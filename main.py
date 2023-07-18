import time
import itertools
import pikepdf


arq_pdf = 'dados/teste.pdf'
maiusculos = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
minusculos = 'abcdefghijklmnopqrstuvwxyz'
digitos = '0123456789'
caracteres = minusculos + digitos
tamanho = 3


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
        return password, None
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
          f'--> Senha atual: {pwd[1]} '
          f'--> Tempo estimado: {tempo_estimado / 60:.2f} minutos.', end='')


def main():
    total_passwords = len(caracteres) ** tamanho
    inicio = time.time()
    print(f'Numero total de combinações: {total_passwords:,}\n')
    for index, password in enumerate(gerar(tamanho)):
        resultado = quebrar_senha(password)
        if resultado[0] is None:
            print("\n\n-----ENCONTRADO-----")
            print("A senha encontrada é: ", password[0])
            tempo_decorrido = time.time() - inicio
            print(f"\nTempo decorrido: {tempo_decorrido:.2f} segundos")
            terminate(0)
        else:
            print_stats(index, password, inicio)
            continue


if __name__ == '__main__':
    main()
    print('Não encontrado no range especificado.')
    quit(5)
