import time
import pikepdf
import itertools
import concurrent.futures

arq_pdf = '/home/gustavo/Downloads/digitos.PDF'
maiusculos = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
minusculos = 'abcdefghijklmnopqrstuvwxyz'
digitos = '0123456789'
caracteres = digitos
combinacoes = []
tamanho = 6
num_threads = 1


def lista_senha(arq):
    # Carregar lista de senhas pré-definidas
    with open(arq) as file:
        passwords_list = file.readlines()
        total_passwords = len(passwords_list)


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


def print_stats(index, password, inicio):
    scanning = (index / len(caracteres) ** tamanho) * 100
    percentil = "{:.3f}".format(round(scanning, 3))
    tempo_decorrido = time.time() - inicio
    senhas_restantes = len(caracteres) ** tamanho - index - 1
    tentativas_por_segundo = index / tempo_decorrido if tempo_decorrido > 0 else 0
    tempo_estimado = senhas_restantes / tentativas_por_segundo if tentativas_por_segundo > 0 else 0
    print(f'\rProgresso total: {percentil} '
          f'--> Senha atual: {password[1]} '
          f'--> Tempo estimado: {tempo_estimado / 60:.2f} minutos.', end='')


def main():
    total_passwords = len(caracteres) ** tamanho
    inicio = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        tentativas = gerar(tamanho)
        resultados = executor.map(quebrar_senha, tentativas)

        for index, password in enumerate(resultados):
            if password[0] is not None:
                print("\n\n-----ENCONTRADO-----")
                print("A senha encontrada é: ", password[0])
                terminate(0)
            else:
                print_stats(index, password, inicio)

    tempo_decorrido = time.time() - inicio
    print(f"\nTempo decorrido: {tempo_decorrido:.2f} segundos")


if __name__ == '__main__':
    main()
    print('Não encontrado no range especificado.')
    quit(5)
