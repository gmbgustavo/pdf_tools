# Gera um dump "em branco" para Mifare Classic 1K (1024 bytes)
with open("blank.mfd", "wb") as f:
    for sector in range(16):  # 16 setores
        for block in range(4):  # 4 blocos por setor
            if block == 3:  # Bloco de trailer
                # Chave A (FFFFFFFFFFFF) + Acesso (FF078069) + Chave B (FFFFFFFFFFFF)
                f.write(bytes.fromhex("FFFFFFFFFFFF FF078069 FFFFFFFFFFFF"))
            else:  # Blocos de dados
                # 16 bytes zerados
                f.write(bytes.fromhex("00000000000000000000000000000000"))
