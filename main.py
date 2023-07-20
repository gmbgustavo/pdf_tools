import time
import itertools
import pikepdf
from colorama import Fore


arq_pdf = 'dados/digitos.PDF'
maiusculos = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
minusculos = 'abcdefghijklmnopqrstuvwxyz'
digitos = '0123456789'
caracteres = digitos
tamanho = 6


def terminate(cod):
    quit(cod)


def gerar(size):
    # Gerar todas as combinações possĩveis por força bruta
    for comb in itertools.product(caracteres, repeat=size):
        senha = ''.join(comb)
        yield senha


def quebrar_senha(password):
    try:
        with pikepdf.open(arq_pdf, password=password.strip()):
            return password, None
    except pikepdf.PasswordError:
        return None, password
    except FileNotFoundError:
        print(f'Arquivo {arq_pdf} não encontrado.')
        terminate(2)


def print_stats(idx, pwd, start):
    scanning = (idx / len(caracteres) ** tamanho) * 100
    percentil = "{:.3f}".format(round(scanning, 3))
    tempo_decorrido = time.time() - start
    senhas_restantes = len(caracteres) ** tamanho - idx - 1
    tentativas_por_segundo = idx / tempo_decorrido if tempo_decorrido > 0 else 0
    tempo_estimado = senhas_restantes / tentativas_por_segundo if tentativas_por_segundo > 0 else 0
    print(f'\rProgresso total: {percentil} '
          f'--> Senha atual: {pwd} '
          f'--> Tempo estimado: {tempo_estimado / 60:.2f} minutos.', end='')


def main():
    total_passwords = len(caracteres) ** tamanho
    inicio = time.time()
    print(f'Numero total de combinações: {total_passwords:,}\n')
    for index, password in enumerate(gerar(tamanho)):
        resultado = quebrar_senha(password)
        if resultado[0] is not None:
            print(Fore.LIGHTBLUE_EX + "\n\n-----ENCONTRADO-----" + Fore.LIGHTWHITE_EX)
            print("A senha encontrada é: " + Fore.GREEN, password)
            tempo_decorrido = (time.time() - inicio) / 60
            print(Fore.LIGHTWHITE_EX + f"\nTempo decorrido: {tempo_decorrido:.2f} minutos")
            terminate(0)
        else:
            print_stats(index, password, inicio)
            continue


if __name__ == '__main__':
    main()
    print(Fore.RED + '\nNão encontrado no range especificado.')
    quit(5)
