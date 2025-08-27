import math
from colorama import Fore


def sieve_small(limit):
    """Gera primos até limit usando Crivo de Eratóstenes."""
    is_prime = [True] * (limit + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(math.sqrt(limit)) + 1):
        if is_prime[i]:
            for j in range(i * i, limit + 1, i):
                is_prime[j] = False
    return [i for i in range(2, limit + 1) if is_prime[i]]


def count_primes_in_segment(low, high, small_primes):
    """Conta primos no segmento [low, high] usando Crivo Segmentado."""
    if low > high:
        return 0
    if high < 2:
        return 0

    block_size = high - low + 1
    is_prime = [True] * block_size

    # Marcar 0 e 1 como não primos se estiverem no intervalo
    if low <= 1:
        for i in range(low, min(2, high + 1)):
            is_prime[i - low] = False

    for p in small_primes:
        if p * p > high:
            break
        # Encontrar o primeiro múltiplo de p no segmento
        start = max(low, p * p)
        start = ((start + p - 1) // p) * p
        for j in range(start, high + 1, p):
            if j != p:  # Não marcar o próprio p se for primo
                is_prime[j - low] = False

    # Contar os primos (True na lista)
    count = sum(1 for val in is_prime if val)
    return count


if __name__ == '__main__':
    # Parâmetros do intervalo e tamanho do bloco
    start = 2
    end = 1_000_000_000
    block_size = 1_000_000

    # Pré-computar primos até sqrt(end)
    small_limit = int(math.sqrt(end)) + 1
    small_primes = sieve_small(small_limit)

    # Calcular o número de blocos usando divisão inteira
    num_blocks = (end - start + 1) // block_size
    if (end - start + 1) % block_size != 0:
        num_blocks += 1

    # Contar primos em cada bloco
    total_primes = 0
    for i in range(num_blocks):
        block_start = start + i * block_size
        block_end = min(block_start + block_size - 1, end)
        primes_in_block = count_primes_in_segment(block_start, block_end, small_primes)
        total_primes += primes_in_block
        print(f"Primos no intervalo [{block_start:,} - {block_end:,}]: {primes_in_block:,}".replace(",", "."))

    # Exibir o total
    print(f"Total de primos no intervalo [{start:,} - {end:,}]: {total_primes:,}".replace(",", "."))