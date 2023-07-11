import time
import pikepdf
import itertools

arq_pdf = "/home/gustavo/Downloads/teste.pdf"
maiusculos = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
minusculos = 'abcdefghijklmnopqrstuvwxyz'
digitos = '0123456789'
caracteres = minusculos + maiusculos + digitos
combinacoes = []
tamanho = 5


def lista_senha(arq):
    # Carregar lista de senhas
    with open(arq) as file:
        passwords_list = file.readlines()
        total_passwords = len(passwords_list)


def gerar(size):
    for comb in itertools.product(caracteres, repeat=size):
        senha = ''.join(comb)
        yield senha


def main():
    total_passwords = len(caracteres) ** tamanho
    inicio = time.time()
    for index, password in enumerate(gerar(tamanho)):
        try:
            with pikepdf.open(arq_pdf, password=password.strip()) as pdf_file:
                print("\n\n-----ENCONTRADO-----")
                print("File is Unlocked and the password is: ", password)
                break
        # Se o arquivo não for encontrado
        except FileNotFoundError:
            print(f'\nArquivo {arq_pdf} não encontradao.')
            quit(2)
        # Se a senha falhar
        except pikepdf.PasswordError:
            scanning = (index / total_passwords) * 100
            percentil = "{:.3f}".format(round(scanning, 3))
            tempo_decorrido = time.time() - inicio
            senhas_restantes = total_passwords - index - 1
            tentativas_por_segundo = index / tempo_decorrido if tempo_decorrido > 0 else 0
            tempo_estimado = senhas_restantes / tentativas_por_segundo if tentativas_por_segundo > 0 else 0
            print(f'\rProgresso total: {percentil} '
                  f'--> Senha atual: {password} '
                  f'--> Tempo estimado = {tempo_estimado / 3600}', end='')
            continue


if __name__ == '__main__':
    main()
