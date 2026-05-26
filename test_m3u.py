import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re
from pathlib import Path

# Configurações
ARQUIVO_ENTRADA = "brasiltv.m3u"
ARQUIVO_SAIDA = "Brasil_TV_Funcionando.m3u"
TIMEOUT = 8  # segundos
MAX_THREADS = 8
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def is_url_working(url):
    """Testa se o link de stream está funcionando"""
    try:
        # Para streams HLS/m3u8, um HEAD rápido costuma ser suficiente
        response = requests.head(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        if response.status_code in (200, 206, 302, 301):
            return True

        # Se HEAD falhar, tenta GET pequeno
        response = requests.get(url, timeout=TIMEOUT, headers=HEADERS, stream=True, allow_redirects=True)
        return response.status_code in (200, 206)

    except Exception:
        return False


def parse_m3u(file_path):
    """Lê o arquivo M3U e retorna lista de (extinf_line, url)"""
    channels = []
    current_extinf = None

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#EXTINF:'):
                current_extinf = line
            elif line and not line.startswith('#') and current_extinf:
                channels.append((current_extinf, line))
                current_extinf = None
    return channels


def main():
    print(f"Carregando {ARQUIVO_ENTRADA}...")
    channels = parse_m3u(ARQUIVO_ENTRADA)
    print(f"Encontrados {len(channels)} canais para testar.\n")

    working_channels = []
    total = len(channels)

    print(f"Testando com {MAX_THREADS} threads (timeout {TIMEOUT}s)...\n")

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_channel = {executor.submit(is_url_working, url): (extinf, url)
                             for extinf, url in channels}

        for i, future in enumerate(as_completed(future_to_channel), 1):
            extinf, url = future_to_channel[future]
            try:
                if future.result():
                    working_channels.append((extinf, url))
                    print(f"✅ [{i}/{total}] Funcionando: {extinf.split(',')[-1]}")
                else:
                    print(f"❌ [{i}/{total}] Falhou: {extinf.split(',')[-1]}")
            except:
                print(f"❌ [{i}/{total}] Erro: {extinf.split(',')[-1]}")

    # Gera novo arquivo
    with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        f.write(f"# Playlist gerada em {time.strftime('%Y-%m-%d %H:%M')} - Apenas links funcionando\n\n")

        for extinf, url in working_channels:
            f.write(extinf + "\n")
            f.write(url + "\n\n")

    print(f"\n✅ Concluído!")
    print(f"Total testado: {total}")
    print(f"Funcionando: {len(working_channels)}")
    print(f"Arquivo salvo como: {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()