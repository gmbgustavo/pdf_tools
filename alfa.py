
TABELA = {"A": "Д", "a": "а",
          "B": "В", "b": "в",
          "C": "С", "c": "с",
          "D": "Đ", "d": "đ",
          "E": "Е", "e": "е",
          "F": "Ϝ", "f": "Ϝ",
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
          "V": "V",
          "W": "Ш", "w": "ш",
          "Y": "У", "y": "у"}


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
