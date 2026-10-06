"""Forca bruta de senha de PDF -- versao otimizada do senha.py.

Mesmas senhas testadas e mesma interface do original, com quatro mudancas:

1. Verificacao rapida (pdfcrypt + pycryptodome): a senha e checada aplicando o
   handler de seguranca padrao do PDF (R2-R6) direto nos bytes do arquivo, sem
   abrir o documento -- ~550 us/tentativa viram ~6 us (R2), ~100 us (R3/R4),
   ~2 us (R5) e ~2,7 ms (R6/AES-256). Se o dicionario /Encrypt nao puder ser
   lido ou o pycryptodome faltar, cai automaticamente para pikepdf.open
   (lendo o arquivo uma vez e abrindo de memoria, ~25% mais rapido).
2. Paralelismo: o espaco de busca e dividido entre os nucleos.
3. Progresso debitado: o original chama print_stats() em TODAS as tentativas;
   aqui a linha e atualizada a cada ~0,5 s, com ETA sobre a taxa medida.
4. Ao encontrar, os demais processos param e a senha e reconferida abrindo o
   PDF com pikepdf antes de ser anunciada.

O paralelismo usa multiprocessing.Process + memoria compartilhada (Array/Value),
sem filas nem pipes -- mais simples de sincronizar, sem pickling do espaco de
busca e sem overhead de RPC por tentativa.

Uso:
    python senha_otimizado.py
    python senha_otimizado.py --pdf boleto.PDF --tamanho 6
    python senha_otimizado.py --caracteres alfanumerico --tamanho 4
    python senha_otimizado.py --caracteres 0123456789 --tamanho 8 --processos 8
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import sys
import time
from typing import Callable, Optional

try:
    from colorama import Fore, Style
    _TEM_COR = True
except ImportError:                           # colorama e opcional
    class Fore:                               # type: ignore
        LIGHTBLUE_EX = LIGHTGREEN_EX = LIGHTRED_EX = LIGHTWHITE_EX = ""
    class Style:                              # type: ignore
        RESET_ALL = ""
    _TEM_COR = False

import pdfcrypt

# ------------------------------------------------------------------ constantes

ARQ_PDF_PADRAO = './boleto.pdf'
TAMANHO_PADRAO = 7
INTERVALO_PADRAO = 0.5
RELATORIO_A_CADA = 64                         # tentativas entre atualizacoes do contador
CHECAGEM_PARADA_S = 0.05                      # intervalo minimo entre consultas de parada
POLL_S = 0.02                                 # granularidade do monitor no processo pai
TAM_MAX_SENHA = 120                           # limite do buffer compartilhado

CONJUNTOS = {
    'digitos': '0123456789',
    'minusculos': 'abcdefghijklmnopqrstuvwxyz',
    'maiusculos': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    'letras': 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
    'alfanumerico': '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
    'hexadecimal': '0123456789abcdef',
    'imprimiveis': ''.join(chr(c) for c in range(32, 127)),
}


# ------------------------------------------------------------- processo filho

def _montar_gerador(charset: str, tamanho: int) -> Callable[[int], bytes]:
    """Funcao(indice) -> senha em bytes, em O(tamanho), sem varrer a faixa anterior."""
    if charset == '0123456789' and tamanho <= 18:
        formato = b'%0' + str(tamanho).encode() + b'd'

        def gerar_digitos(i: int) -> bytes:
            return formato % i

        return gerar_digitos

    alfabeto = charset.encode('latin-1', 'replace')
    base = len(alfabeto)

    def gerar_generico(i: int) -> bytes:
        buf = bytearray(tamanho)
        for k in range(tamanho - 1, -1, -1):
            i, resto = divmod(i, base)
            buf[k] = alfabeto[resto]
        return bytes(buf)

    return gerar_generico


def _montar_verificador(pdf: str, modo: str) -> Callable[[bytes], bool]:
    """Verificador usado dentro de cada processo filho."""
    if modo == 'rapido':
        params = pdfcrypt.parse_params(pdf)
        verificador = pdfcrypt.make_checker(params) if params else None
        if verificador is not None:
            return verificador
        # rede de seguranca: nunca deveria chegar aqui, o pai ja validou
    import io

    import pikepdf
    with open(pdf, 'rb') as f:
        blob = f.read()

    def verificador_pikepdf(senha: bytes) -> bool:
        try:
            with pikepdf.open(io.BytesIO(blob), password=senha.decode('latin-1')):
                return True
        except pikepdf.PasswordError:
            return False

    return verificador_pikepdf


def _trabalhador(inicio: int, fim: int, charset: str, tamanho: int, modo: str,
                 pdf: str, slot: int, progresso, achou, buffer, tam_buffer) -> None:
    """Testa os indices [inicio, fim) da sua fatia do espaco de busca."""
    verificador = _montar_verificador(pdf, modo)
    gerar = _montar_gerador(charset, tamanho)

    contador = 0
    ultima_checagem = time.perf_counter()
    for i in range(inicio, fim):
        senha = gerar(i)
        if verificador(senha):
            progresso[slot] = i - inicio + 1
            dados = senha[:TAM_MAX_SENHA]
            buffer[0:len(dados)] = dados
            tam_buffer.value = len(dados)
            achou.value = 1
            return
        contador += 1
        if contador >= RELATORIO_A_CADA:
            progresso[slot] = i - inicio + 1
            contador = 0
            agora = time.perf_counter()
            if agora - ultima_checagem >= CHECAGEM_PARADA_S:
                ultima_checagem = agora
                if achou.value:               # outro processo ja encontrou
                    return
    progresso[slot] = fim - inicio


# ------------------------------------------------------------------ auxiliares

def _confirmar_com_pikepdf(pdf: str, senha: str) -> bool:
    try:
        import pikepdf
    except ImportError:
        return True
    try:
        with pikepdf.open(pdf, password=senha):
            return True
    except pikepdf.PasswordError:
        return False


def _abre_sem_senha(pdf: str) -> bool:
    """True se o PDF abre sem senha -- nesse caso nao ha o que quebrar."""
    try:
        import pikepdf
        with pikepdf.open(pdf):
            return True
    except Exception:
        return False


def _dividir_faixas(total: int, partes: int) -> list[tuple[int, int]]:
    """Fatias contiguas e do mesmo tamanho (custo por tentativa e constante)."""
    tamanho = total // partes
    sobra = total % partes
    faixas = []
    inicio = 0
    for k in range(partes):
        fim = inicio + tamanho + (1 if k < sobra else 0)
        faixas.append((inicio, fim))
        inicio = fim
    return faixas


def _formatar_segundos(seg: float) -> str:
    return f'{seg:.2f} segundos' if seg < 60 else f'{seg / 60:.2f} minutos'


def _formatar_eta(seg: float) -> str:
    if seg < 1:
        return '0,0 min'
    return f'{seg / 60:,.2f} min'


# ------------------------------------------------------------------ principal

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description='Forca bruta de senha de PDF (versao otimizada).')
    parser.add_argument('--pdf', default=ARQ_PDF_PADRAO, help='arquivo PDF')
    parser.add_argument('--tamanho', type=int, default=TAMANHO_PADRAO,
                        help=f'tamanho da senha (padrao: {TAMANHO_PADRAO})')
    parser.add_argument('--caracteres', default='digitos',
                        help='digitos|minusculos|maiusculos|letras|alfanumerico|'
                             'hexadecimal|imprimiveis ou um conjunto literal')
    parser.add_argument('--processos', type=int, default=os.cpu_count() or 1,
                        help='numero de processos (padrao: todos os nucleos)')
    parser.add_argument('--intervalo', type=float, default=INTERVALO_PADRAO,
                        help='intervalo de atualizacao do progresso, em segundos')
    parser.add_argument('--forcar-pikepdf', action='store_true',
                        help='ignora o verificador rapido e usa pikepdf.open')
    parser.add_argument('--sem-cor', action='store_true', help='desliga as cores')
    args = parser.parse_args(argv)

    charset = CONJUNTOS.get(args.caracteres.strip().lower(), args.caracteres)
    if not charset:
        parser.error('conjunto de caracteres vazio')
    if not 1 <= args.tamanho <= TAM_MAX_SENHA:
        parser.error(f'--tamanho deve ficar entre 1 e {TAM_MAX_SENHA}')
    if args.sem_cor or not _TEM_COR:
        for nome in ('LIGHTBLUE_EX', 'LIGHTGREEN_EX', 'LIGHTRED_EX', 'LIGHTWHITE_EX'):
            setattr(Fore, nome, '')
        Style.RESET_ALL = ''

    pdf = args.pdf
    if not os.path.isfile(pdf):
        print(Fore.LIGHTRED_EX + f'Arquivo {pdf} nao encontrado.' + Style.RESET_ALL)
        return 2
    if _abre_sem_senha(pdf):
        print(Fore.LIGHTBLUE_EX
              + 'O PDF abre sem senha: nao ha senha a quebrar.' + Style.RESET_ALL)
        return 0

    total = len(charset) ** args.tamanho
    processos = max(1, min(args.processos, total, os.cpu_count() or 1))

    # -------- escolha do verificador (os parametros sao lidos sempre, por diagnostico)
    params = pdfcrypt.parse_params(pdf)
    modo = 'pikepdf'
    if not args.forcar_pikepdf and params is not None \
            and pdfcrypt.make_checker(params) is not None:
        modo = 'rapido'

    if modo == 'rapido':
        detalhe = (f'R={params.revisao} V={params.versao} '
                   f'chave={params.tam_chave * 8} bits')
    else:
        detalhe = 'pikepdf.open'
        if args.forcar_pikepdf:
            detalhe += ' (forcado na linha de comando)'
        elif params is None and not pdfcrypt.parece_criptografado(pdf):
            detalhe += ' (o PDF parece nao estar criptografado)'
        elif params is None:
            detalhe += ' (parametros de /Encrypt nao reconhecidos)'
        elif not pdfcrypt.TEM_CRYPTO:
            detalhe += ' (pycryptodome ausente)'

    print(f'Arquivo: {pdf}')
    print(f'Verificacao: {modo} -- {detalhe}')
    print(f'Espaco de busca: {len(charset)} caracteres ^ {args.tamanho} '
          f'= {total:,} combinacoes')
    print(f'Processos: {processos} ({total // processos:,} combinacoes cada)\n')

    # -------- estado compartilhado (memoria mapeada, sem pipes)
    progresso = mp.Array('q', processos, lock=False)
    achou = mp.Value('b', 0)
    buffer = mp.Array('c', TAM_MAX_SENHA)
    tam_buffer = mp.Value('i', 0)

    faixas = _dividir_faixas(total, processos)
    filhos = [
        mp.Process(
            target=_trabalhador,
            args=(inicio, fim, charset, args.tamanho, modo, pdf, slot,
                  progresso, achou, buffer, tam_buffer),
            name=f'quebrador-{slot}',
            daemon=True,
        )
        for slot, (inicio, fim) in enumerate(faixas)
    ]

    inicio = time.perf_counter()
    for filho in filhos:
        filho.start()

    proximo_relatorio = inicio + args.intervalo
    interrompido = False
    try:
        while True:
            vivos = [f for f in filhos if f.is_alive()]
            if achou.value or not vivos:
                break
            time.sleep(POLL_S)
            agora = time.perf_counter()
            if agora >= proximo_relatorio:
                proximo_relatorio = agora + args.intervalo
                feitas = sum(progresso[:])
                decorrido = agora - inicio
                taxa = feitas / decorrido if decorrido > 0 else 0.0
                eta = (total - feitas) / taxa if taxa > 0 else 0.0
                print(f'\rProgresso total: {feitas / total * 100:7.3f}% '
                      f'--> {feitas:,}/{total:,} '
                      f'--> {taxa:,.0f} senhas/s '
                      f'--> ETA {_formatar_eta(eta)}  [{modo}]',
                      end='', flush=True)
    except KeyboardInterrupt:
        interrompido = True
        print('\n\nInterrompido pelo usuario.')

    for filho in filhos:                      # os que acharam ja sairam sozinhos
        if filho.is_alive():
            filho.terminate()
    for filho in filhos:
        filho.join(timeout=5)
    decorrido = time.perf_counter() - inicio

    feitas = sum(progresso[:])
    print(f'\rProgresso total: {feitas / total * 100:7.3f}% '
          f'--> {feitas:,}/{total:,} '
          f'--> {feitas / decorrido if decorrido else 0:,.0f} senhas/s'
          f'                                          ')

    # -------- resultado
    if achou.value:
        senha = bytes(buffer[:tam_buffer.value]).decode('latin-1')
        if not _confirmar_com_pikepdf(pdf, senha):
            print(Fore.LIGHTRED_EX
                  + 'A senha candidata nao abriu o PDF; verificador inconsistente.'
                  + Style.RESET_ALL)
            return 4
        print(Fore.LIGHTBLUE_EX + '-----ENCONTRADO-----' + Style.RESET_ALL)
        print('A senha encontrada e: ' + Fore.LIGHTGREEN_EX + senha + Style.RESET_ALL)
        print(f'\nTempo decorrido: {_formatar_segundos(decorrido)}')
        return 0

    if interrompido:
        return 130

    codigos = [f.exitcode for f in filhos]
    if any(c not in (0, None) for c in codigos):
        print(Fore.LIGHTRED_EX
              + f'Alguns processos terminaram com erro (exit codes: {codigos}).'
              + Style.RESET_ALL)
        return 3

    print(Fore.LIGHTRED_EX + 'Nao encontrado no range especificado.'
          + Style.RESET_ALL)
    print(f'Tempo decorrido: {_formatar_segundos(decorrido)}')
    return 5


if __name__ == '__main__':
    sys.exit(main())
