import os
from fpdf import FPDF


def images_to_pdf(pasta_img, saida_pdf):
    pdf = FPDF()
    tipo_img = ['.jpg', '.jpeg', '.jpe']
    count = 1

    for arquivo in os.listdir(pasta_img):
        if any(arquivo.lower().endswith(ext) for ext in tipo_img):
            print(f'Adicionando imagem {arquivo} ({count} de {len(os.listdir(pasta_img))})')
            image_path = os.path.join(pasta_img, arquivo)
            pdf.add_page()
            pdf.image(image_path, x=10, y=10, w=190)
            count += 1

    pdf.output(saida_pdf)


if __name__ == "__main__":
    pasta_origem = "img"
    output_pdf = "output.pdf"
    images_to_pdf(pasta_origem, output_pdf)
