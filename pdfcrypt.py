"""Leitura dos parametros de criptografia de um PDF e verificacao rapida de senha.

Abrir o PDF inteiro com pikepdf/qpdf custa ~550 us por tentativa (para R<=4) e
~11 ms (para R=6, AES-256), independentemente do tamanho do arquivo: o custo e
o setup do documento, nao o parsing. Como a validacao da senha depende apenas
do dicionario /Encrypt e de /ID[0] -- ambos legiveis sem senha --, este modulo
le esses dados direto dos bytes do arquivo e aplica os algoritmos do handler
padrao (ISO 32000-1 7.6.3 para R2-R4, ISO 32000-2 7.6.4 para R5/R6), que sao
~10 a ~100 vezes mais baratos.

Nada aqui substitui a verificacao final: qualquer candidato aprovado deve ser
confirmado abrindo o PDF com pikepdf (feito por senha_otimizado.py).

Bibliotecas: stdlib + pycryptodome (RC4/AES em C). Sem pycryptodome o modulo
apenas informa que nao consegue verificar (make_checker devolve None).
"""
from __future__ import annotations

import re
import struct
from hashlib import md5, sha256, sha384, sha512
from typing import Callable, NamedTuple, Optional

try:  # pragma: no cover - depende do ambiente
    from Crypto.Cipher import AES, ARC4
    _TEM_CRYPTO = True
except ImportError:  # pragma: no cover
    _TEM_CRYPTO = False

TEM_CRYPTO = _TEM_CRYPTO

# Acesso direto a biblioteca C do ARC4 do pycryptodome: evita a criacao de um
# objeto Python por passada de RC4 (~4 us -> ~2,5 us por passada, e o Algoritmo 5
# precisa de 20 passadas por senha). Se algo mudar, o caminho de alto nivel
# continua valendo.
try:  # pragma: no cover - depende da versao do pycryptodome
    import ctypes as _ctypes

    from Crypto.Util._raw_api import (VoidPointer, c_size_t, c_uint8_ptr,
                                      create_string_buffer,
                                      load_pycryptodome_raw_lib)
    _LIB_ARC4 = load_pycryptodome_raw_lib("Crypto.Cipher._ARC4", """
        int ARC4_stream_encrypt(void *rc4State, const uint8_t in[], uint8_t out[], size_t len);
        int ARC4_stream_init(uint8_t *key, size_t keylen, void **pRc4State);
        int ARC4_stream_destroy(void *rc4State);
    """)
except Exception:  # pragma: no cover
    _LIB_ARC4 = None

# ---------------------------------------------------------------- constantes

PADDING = bytes([
    0x28, 0xBF, 0x4E, 0x5E, 0x4E, 0x75, 0x8A, 0x41, 0x64, 0x00, 0x4E, 0x56,
    0xFF, 0xFA, 0x01, 0x08, 0x2E, 0x2E, 0x00, 0xB6, 0xD0, 0x68, 0x3E, 0x80,
    0x2F, 0x0C, 0xA9, 0xFE, 0x64, 0x53, 0x69, 0x7A,
])

_WS = b"\x00\t\n\x0c\r "
_DELIM = b"()<>[]{}/%"
_NUM_RE = re.compile(rb"[+-]?(?:\d+\.\d*|\.\d+|\d+)")
_INT_RE = re.compile(rb"[+-]?\d+")
_REF_RE = re.compile(rb"\s*(\d{1,10})\s+(\d{1,5})\s+R(?![A-Za-z0-9])")


class EncryptionParams(NamedTuple):
    revisao: int          # /R
    versao: int           # /V
    tam_chave: int        # bytes da chave (5, 16 ou 32)
    O: bytes
    U: bytes
    P: int
    metadados_cripto: bool  # /EncryptMetadata
    id0: bytes
    filtro: bytes


# ------------------------------------------------------------------ lexer PDF

def _pular_espaco(data: bytes, i: int) -> int:
    n = len(data)
    while i < n:
        c = data[i]
        if c in _WS:
            i += 1
        elif c == 0x25:                      # comentario: % ate fim da linha
            while i < n and data[i] not in (0x0A, 0x0D):
                i += 1
        else:
            break
    return i


def _ler_nome(data: bytes, i: int):
    i += 1                                   # consome '/'
    n = len(data)
    j = i
    while j < n and data[j] not in _WS and data[j] not in _DELIM:
        j += 1
    bruto = data[i:j]
    if b'#' in bruto:                        # escapes #XX
        saida = bytearray()
        k = 0
        while k < len(bruto):
            if bruto[k] == 0x23 and k + 2 < len(bruto):
                try:
                    saida.append(int(bruto[k + 1:k + 3], 16))
                    k += 3
                    continue
                except ValueError:
                    pass
            saida.append(bruto[k])
            k += 1
        return bytes(saida), j
    return bruto, j


def _ler_string_literal(data: bytes, i: int):
    i += 1
    n = len(data)
    saida = bytearray()
    profundidade = 1
    while i < n:
        c = data[i]
        if c == 0x5C:                        # '\'
            i += 1
            if i >= n:
                break
            e = data[i]
            if e in b'nrtbf':
                saida.append({0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}[e])
                i += 1
            elif e in b'()\\':
                saida.append(e)
                i += 1
            elif 0x30 <= e <= 0x37:          # octal ate 3 digitos
                j = i
                while j < n and j < i + 3 and 0x30 <= data[j] <= 0x37:
                    j += 1
                saida.append(int(data[i:j], 8) & 0xFF)
                i = j
            elif e in (0x0A, 0x0D):          # continuacao de linha
                i += 1
                if e == 0x0D and i < n and data[i] == 0x0A:
                    i += 1
            else:
                saida.append(e)
                i += 1
            continue
        if c == 0x28:
            profundidade += 1
        elif c == 0x29:
            profundidade -= 1
            if profundidade == 0:
                return bytes(saida), i + 1
        saida.append(c)
        i += 1
    raise ValueError("string literal nao terminada")


def _ler_string_hex(data: bytes, i: int):
    j = data.index(b'>', i)
    bruto = re.sub(rb'[^0-9A-Fa-f]', b'', data[i + 1:j])
    if len(bruto) % 2:
        bruto += b'0'
    return bytes.fromhex(bruto.decode('ascii')), j + 1


def _parse_valor(data: bytes, i: int):
    i = _pular_espaco(data, i)
    c = data[i:i + 1]
    if c == b'<':
        if data[i:i + 2] == b'<<':
            return _parse_dicionario(data, i)
        return _ler_string_hex(data, i)
    if c == b'(':
        return _ler_string_literal(data, i)
    if c == b'/':
        return _ler_nome(data, i)
    if c == b'[':
        itens = []
        i += 1
        while True:
            i = _pular_espaco(data, i)
            if data[i:i + 1] == b']':
                return itens, i + 1
            valor, i = _parse_valor(data, i)
            itens.append(valor)
    if c == b']' or c == b'':
        raise ValueError("token inesperado")
    if data.startswith(b'true', i):
        return True, i + 4
    if data.startswith(b'false', i):
        return False, i + 5
    if data.startswith(b'null', i):
        return None, i + 4
    m = _NUM_RE.match(data, i)
    if m:
        bruto = m.group()
        fim = m.end()
        if b'.' in bruto:
            return float(bruto), fim
        valor = int(bruto)
        mref = _REF_RE.match(data, fim)
        if mref:                              # referencia indireta: n g R
            return (int(mref.group(1)), int(mref.group(2))), mref.end()
        return valor, fim
    # palavra-chave desconhecida: consome ate o proximo delimitador
    j = i
    while j < len(data) and data[j] not in _WS and data[j] not in _DELIM:
        j += 1
    if j == i:
        raise ValueError("token desconhecido")
    return data[i:j], j


def _parse_dicionario(data: bytes, i: int):
    i += 2                                    # consome '<<'
    dicionario = {}
    while True:
        i = _pular_espaco(data, i)
        if data[i:i + 2] == b'>>':
            return dicionario, i + 2
        if data[i:i + 1] != b'/':
            raise ValueError("chave de dicionario invalida")
        chave, i = _ler_nome(data, i)
        valor, i = _parse_valor(data, i)
        dicionario[chave] = valor


# -------------------------------------------------- localizacao de /Encrypt

def _achar_dicionario_encrypt(data: bytes) -> Optional[dict]:
    """Devolve o dicionario /Encrypt (indireto ou direto) ou None."""
    posicoes = [m.start() for m in re.finditer(rb'/Encrypt\b', data)]
    for pos in reversed(posicoes):            # o trailer util e o ultimo
        i = pos + len(b'/Encrypt')
        try:
            valor, _ = _parse_valor(data, i)
        except Exception:
            continue
        if isinstance(valor, dict):
            if b'R' in valor and b'O' in valor and b'U' in valor:
                return valor
            continue
        if isinstance(valor, tuple) and len(valor) == 2:   # referencia indireta
            num, ger = valor
            padrao = re.compile(
                rb'(?<![0-9])' + str(num).encode() + rb'\s+' + str(ger).encode() + rb'\s+obj'
            )
            for m in padrao.finditer(data):
                try:
                    obj, _ = _parse_valor(data, m.end())
                except Exception:
                    continue
                if isinstance(obj, dict) and b'R' in obj and b'O' in obj:
                    return obj
    # ultimo recurso: qualquer dicionario com /Filter /Standard
    for m in re.finditer(rb'/Filter\s*/Standard', data):
        inicio = data.rfind(b'<<', 0, m.start())
        while inicio != -1:
            try:
                obj, _ = _parse_valor(data, inicio)
            except Exception:
                obj = None
            if isinstance(obj, dict) and b'R' in obj and b'O' in obj and b'U' in obj:
                return obj
            inicio = data.rfind(b'<<', 0, inicio)
    return None


def _achar_id0(data: bytes) -> Optional[bytes]:
    pos = data.rfind(b'/ID')
    while pos != -1:
        try:
            valor, _ = _parse_valor(data, pos + len(b'/ID'))
        except Exception:
            valor = None
        if isinstance(valor, list) and valor and isinstance(valor[0], bytes) and valor[0]:
            return valor[0]
        pos = data.rfind(b'/ID', 0, pos)
    return None


def parece_criptografado(caminho: str) -> bool:
    """True se o arquivo tem um dicionario /Encrypt (mesmo que nao seja lido)."""
    with open(caminho, 'rb') as f:
        return b'/Encrypt' in f.read()


def parse_params(caminho: str) -> Optional[EncryptionParams]:
    """Le /Encrypt e /ID[0] do arquivo. None se nao for possivel."""
    with open(caminho, 'rb') as f:
        data = f.read()
    dicionario = _achar_dicionario_encrypt(data)
    if dicionario is None:
        return None
    try:
        R = int(dicionario[b'R'])
        V = int(dicionario.get(b'V', 1))
        O = dicionario[b'O']
        U = dicionario[b'U']
        P = int(dicionario[b'P'])
        filtro = dicionario.get(b'Filter', b'Standard')
        metadados = dicionario.get(b'EncryptMetadata', True)
        comprimento = int(dicionario.get(b'Length', 40))
    except (KeyError, TypeError, ValueError):
        return None
    if filtro != b'Standard':
        return None                           # handler de seguranca publica
    if not isinstance(O, bytes) or not isinstance(U, bytes):
        return None
    if R == 2:
        tam_chave = 5
        if len(O) != 32 or len(U) != 32:
            return None
    elif R in (3, 4):
        tam_chave = max(5, min(16, comprimento // 8 or 5))
        if len(O) < 32 or len(U) < 16:
            return None
    elif R in (5, 6):
        tam_chave = 32
        if len(O) < 48 or len(U) < 48:
            return None
    else:
        return None                           # revisao desconhecida
    id0 = _achar_id0(data)
    if not id0:
        return None
    return EncryptionParams(R, V, tam_chave, O, U, P, bool(metadados), id0, filtro)


# ------------------------------------------------------- algoritmos de senha

def _preencher_senha(senha: bytes) -> bytes:
    return (senha + PADDING)[:32]


def _chave_r2_a_r4(senha: bytes, p: EncryptionParams) -> bytes:
    """Algoritmo 2 do ISO 32000-1 (R2-R4)."""
    h = md5(_preencher_senha(senha))
    h.update(p.O)
    h.update(struct.pack('<i', p.P))
    h.update(p.id0)
    if p.revisao >= 4 and not p.metadados_cripto:
        h.update(b'\xff\xff\xff\xff')
    chave = h.digest()
    if p.revisao >= 3:                        # Algoritmo 3: 50 iteracoes
        n = p.tam_chave
        for _ in range(50):
            chave = md5(chave[:n]).digest()
    return chave[:p.tam_chave]


def _hardened_hash(senha: bytes, salt: bytes, udata: bytes = b'') -> bytes:
    """Algoritmo 2.B do ISO 32000-2 (R6)."""
    k = sha256(senha + salt + udata).digest()
    i = 0
    while True:
        k1 = (senha + k + udata) * 64
        e = AES.new(k[:16], AES.MODE_CBC, k[16:32]).encrypt(k1)
        mod = sum(e[:16]) % 3
        k = (sha256, sha384, sha512)[mod](e).digest()
        i += 1
        if i >= 64 and e[-1] <= i - 32:
            return k[:32]


def make_checker(p: EncryptionParams, dono: bool = True
                 ) -> Optional[Callable[[bytes], bool]]:
    """Devolve check(senha_bytes) -> bool, ou None se a revisao nao for suportada."""
    if not _TEM_CRYPTO:
        return None

    if p.revisao == 2:
        O, id0, U, n = p.O, p.id0, p.U, p.tam_chave
        fixo = struct.pack('<i', p.P)

        def check_r2(senha: bytes) -> bool:
            h = md5(_preencher_senha(senha) + O)
            h.update(fixo)
            h.update(id0)
            return ARC4.new(h.digest()[:n]).encrypt(PADDING) == U

        return check_r2

    if p.revisao in (3, 4):
        O, id0, U, n = p.O, p.id0, p.U, p.tam_chave
        fixo = struct.pack('<i', p.P) + id0
        if not p.metadados_cripto:
            fixo += b'\xff\xff\xff\xff'
        # Algoritmo 5: o valor inicial e MD5(padding + ID[0]); as 19 chaves
        # seguintes sao a chave do ficheiro (que depende da senha candidata)
        # com cada byte em XOR com o contador da iteracao.
        inicial = md5(PADDING + id0).digest()
        # 19 tabelas de traducao (x -> x ^ i) calculadas uma unica vez:
        # bytes.translate roda em C, muito mais rapido que um genexp por senha.
        tabelas = [bytes.maketrans(bytes(range(256)),
                                   bytes(x ^ i for x in range(256)))
                   for i in range(1, 20)]
        U16 = U[:16]

        if _LIB_ARC4 is not None:
            lib = _LIB_ARC4
            tam16 = c_size_t(16)
            tam_chave = c_size_t(n)
            buffer = create_string_buffer(inicial, 16)
            ptr_inicial = c_uint8_ptr(inicial)

            def check_r3(senha: bytes) -> bool:
                h = md5(_preencher_senha(senha) + O)
                h.update(fixo)
                chave = h.digest()
                for _ in range(50):
                    chave = md5(chave[:n]).digest()
                chave = chave[:n]
                # RC4 no lugar (in == out): o handler padrao aplica 20 passadas
                _ctypes.memmove(buffer, ptr_inicial, 16)
                estado = VoidPointer()
                lib.ARC4_stream_init(c_uint8_ptr(chave), tam_chave, estado.address_of())
                lib.ARC4_stream_encrypt(estado.get(), buffer, buffer, tam16)
                lib.ARC4_stream_destroy(estado.get())
                for tabela in tabelas:
                    estado = VoidPointer()
                    lib.ARC4_stream_init(c_uint8_ptr(chave.translate(tabela)),
                                         tam_chave, estado.address_of())
                    lib.ARC4_stream_encrypt(estado.get(), buffer, buffer, tam16)
                    lib.ARC4_stream_destroy(estado.get())
                return buffer.raw[:16] == U16

            return check_r3

        def check_r3(senha: bytes) -> bool:
            h = md5(_preencher_senha(senha) + O)
            h.update(fixo)
            chave = h.digest()
            for _ in range(50):
                chave = md5(chave[:n]).digest()
            chave = chave[:n]
            valor = ARC4.new(chave).encrypt(inicial)
            for tabela in tabelas:
                valor = ARC4.new(chave.translate(tabela)).encrypt(valor)
            return valor[:16] == U16

        return check_r3

    if p.revisao == 5:
        U, O = p.U, p.O

        def check_r5(senha: bytes) -> bool:
            if sha256(senha + U[32:40]).digest() == U[:32]:
                return True
            if dono and len(O) >= 48 and sha256(senha + O[32:40] + U[:48]).digest() == O[:32]:
                return True
            return False

        return check_r5

    if p.revisao == 6:
        U, O = p.U, p.O

        def check_r6(senha: bytes) -> bool:
            if _hardened_hash(senha, U[32:40]) == U[:32]:
                return True
            if dono and len(O) >= 48 and \
                    _hardened_hash(senha, O[32:40], U[:48]) == O[:32]:
                return True
            return False

        return check_r6

    return None


def senha_em_bytes(senha: str) -> bytes:
    """PDF usa PDFDocEncoding/latin-1 na derivacao da chave."""
    return senha.encode('latin-1', 'replace')
