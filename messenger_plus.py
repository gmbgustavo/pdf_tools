import binascii

# Caminho para o arquivo .ple
file_path = 'files/arquivo.ple'

# Número de hashes esperados (conforme identificado pelo John)
num_hashes = 46

# Tamanho do hash HMAC-SHA256 (32 bytes)
hash_size = 32

# Tamanho estimado do salt (vamos tentar 16 bytes, comum em HMAC)
salt_size = 16

# Ler o arquivo binário
with open(file_path, 'rb') as f:
    data = f.read()

# Encontrar a posição de RSA1
rsa1_offset = data.find(b'RSA1') + 4
if rsa1_offset == 3:  # -1 + 4
    print("RSA1 não encontrado no arquivo!")
    exit(1)

print(f"RSA1 encontrado no offset: {rsa1_offset}")

# Tentar extrair hashes e salts
hashes = []
salts = []
offset = rsa1_offset

for i in range(num_hashes):
    # Extrair hash (32 bytes)
    hash_bytes = data[offset:offset + hash_size]
    if len(hash_bytes) != hash_size:
        print(f"Erro: Não há bytes suficientes para hash {i + 1} no offset {offset}")
        break
    hash_hex = binascii.hexlify(hash_bytes).decode('ascii')

    # Extrair salt (tentar 16 bytes antes ou depois do hash)
    # Opção 1: Salt antes do hash
    salt_bytes = data[offset - salt_size:offset]
    if len(salt_bytes) != salt_size:
        # Opção 2: Salt depois do hash
        salt_bytes = data[offset + hash_size:offset + hash_size + salt_size]
        if len(salt_bytes) != salt_size:
            print(f"Erro: Não há bytes suficientes para salt {i + 1}")
            break
    salt_hex = binascii.hexlify(salt_bytes).decode('ascii')

    hashes.append(hash_hex)
    salts.append(salt_hex)

    # Avançar para o próximo bloco (assumindo hash + salt ou apenas hash)
    offset += hash_size + salt_size  # Ajustar conforme a estrutura do arquivo

# Salvar hashes e salts em um arquivo no formato do Hashcat
with open('hash.txt', 'w') as f:
    for h, s in zip(hashes, salts):
        f.write(f"{h}:{s}\n")

print(f"Extraídos {len(hashes)} hashes e salts. Salvo em hash.txt")