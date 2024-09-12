
TABELA = {"A": "Д", "a": "а",
          "B": "В", "b": "в",
          "E": "Е", "e": "е",
          "H": "Н", "h": "н",
          "I": "І", "i": "і",
          "J": "Ј", "j": "ј",
          "l": "I",
          "M": "М", "m": "м",
          "N": "И",
          "O": "О", "o": "о",
          "P": "Р", "p": "р",
          "S": "Ѕ", "s": "ѕ",
          "T": "Т", "t": "т",
          "W": "Ш", "w": "ш",
          "Y": "У", "y": "у" }


def converte(texto: str):
    strout = ''
    for letra in texto:
        if letra in TABELA.keys():
            strout += TABELA[letra]
        else:
            strout += letra
    return strout



if __name__ == "__main__":
    saida = ''
    while saida != '1':
        saida = input('Digite o texto (1 para sair): ')
        print(converte(saida))
    quit(0)
