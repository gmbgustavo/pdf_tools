import itertools


def gerar(tamanho):
    caracteres = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    combinacoes = []

    for comb in itertools.product(caracteres, repeat=tamanho):
        senha = ''.join(comb)
        yield senha


'''
    
    for num in range(0, 10_000_000):
        with open('pass_digitos', 'a') as digitos:
            print('Gerando...\n')
            digitos.write(str(num) + '\n')
            if num % 1000 == 0:
                print(f'\rProgresso: {num}.f', end='')
    
    print('\nGerado.')'''
