import os
import uuid
import smtplib
import requests
from flask import Flask, render_template, request, jsonify
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
from datetime import datetime

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# Configurações do Mercado Pago
MP_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN')
MP_API_BASE_URL = 'https://api.mercadopago.com'

# Configurações de e-mail
EMAIL_SENDER = os.getenv('EMAIL_SENDER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

# Dicionário para armazenar pagamentos pendentes
# (em produção, use um banco de dados)
pending_payments = {}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/criar-pagamento', methods=['POST'])
def criar_pagamento():
    email = request.form.get('email')

    if not email:
        return jsonify({'error': 'E-mail é obrigatório'}), 400

    # Dados para criar o pagamento no Mercado Pago
    payment_data = {
        "transaction_amount": 19.90,
        "description": "E-book: As 50 IAs Mais Poderosas do Mundo (2025)",
        "payment_method_id": "pix",
        "payer": {
            "email": email
        }
    }

    # Gerar uma chave de idempotência única
    idempotency_key = str(uuid.uuid4())

    # Chamada à API do Mercado Pago
    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": idempotency_key  # Header obrigatório
    }

    try:
        response = requests.post(
            f"{MP_API_BASE_URL}/v1/payments",
            json=payment_data,
            headers=headers
        )

        if response.status_code == 201:
            payment_info = response.json()
            payment_id = payment_info['id']
            transaction_data = payment_info['point_of_interaction'][
                'transaction_data']
            qr_code = transaction_data['qr_code_base64']
            pix_copia_cola = transaction_data['qr_code']

            # Armazenar o pagamento pendente
            pending_payments[str(payment_id)] = {
                'email': email,
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
                'idempotency_key': idempotency_key
            }

            # Adicionar prefixo para imagem base64
            qr_code_img = f"data:image/png;base64,{qr_code}"

            return render_template(
                'payment.html',
                qr_code=qr_code_img,
                pix_copia_cola=pix_copia_cola,
                email=email,
                payment_id=payment_id
            )
        else:
            return jsonify({
                'error': 'Erro ao criar pagamento',
                'details': response.json()
            }), response.status_code

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/check-payment/<payment_id>')
def check_payment(payment_id):
    """Verifica o status de um pagamento no Mercado Pago"""
    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}"
    }

    try:
        response = requests.get(
            f"{MP_API_BASE_URL}/v1/payments/{payment_id}",
            headers=headers
        )

        if response.status_code == 200:
            payment_info = response.json()
            status = payment_info['status']

            # Se o pagamento foi aprovado e ainda não enviamos o e-book
            if status == 'approved' and payment_id in pending_payments:
                if pending_payments[payment_id]['status'] != 'approved':
                    # Atualizar status
                    pending_payments[payment_id]['status'] = 'approved'

                    # Enviar e-book
                    email = pending_payments[payment_id]['email']
                    enviar_ebook(email)

            return jsonify({'status': status})
        else:
            return jsonify({
                'error': 'Erro ao verificar pagamento'
            }), response.status_code

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/webhook', methods=['POST'])
def webhook():
    """Recebe notificações de pagamento do Mercado Pago"""
    try:
        data = request.json

        # Verificar se é uma notificação de pagamento
        if data.get('action') == 'payment.updated':
            # Obter ID do pagamento
            payment_id = data.get('data', {}).get('id')

            if not payment_id:
                return jsonify({
                    'error': 'ID de pagamento não encontrado'
                }), 400

            # Verificar status do pagamento
            headers = {
                "Authorization": f"Bearer {MP_ACCESS_TOKEN}"
            }

            response = requests.get(
                f"{MP_API_BASE_URL}/v1/payments/{payment_id}",
                headers=headers
            )

            if response.status_code == 200:
                payment_info = response.json()
                status = payment_info['status']

                # Se o pagamento foi aprovado
                if status == 'approved':
                    # Encontrar o email associado a este pagamento
                    if str(payment_id) in pending_payments:
                        payment_data = pending_payments[str(payment_id)]

                        # Verificar se já processamos este pagamento
                        if payment_data['status'] != 'approved':
                            # Atualizar status
                            payment_data['status'] = 'approved'

                            # Enviar e-book
                            email = payment_data['email']
                            enviar_ebook(email)

                            return jsonify({
                                'success': True,
                                'message': 'E-book enviado com sucesso'
                            })
                    else:
                        # Tentar obter email do próprio pagamento
                        payer_email = payment_info.get('payer', {}).get(
                            'email')
                        if payer_email:
                            enviar_ebook(payer_email)
                            return jsonify({
                                'success': True,
                                'message': 'E-book enviado com sucesso'
                            })

        return jsonify({
            'success': True,
            'message': 'Notificação recebida'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def enviar_ebook(email):
    """Envia o e-book por e-mail para o comprador"""
    try:
        # Criar mensagem de e-mail
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = email
        msg['Subject'] = 'Seu e-book: As 50 IAs Mais Poderosas do Mundo (2025)'

        # Corpo do e-mail
        body = """
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; 
        color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #4361ee;">Seu e-book está aqui! 🎉</h1>
                <p>Olá!</p>
                <p>Muito obrigado pela sua compra! Segue em anexo o seu 
                e-book:</p>
                <p><strong>As 50 IAs Mais Poderosas do Mundo (2025)</strong>
                </p>
                <p>Esperamos que você aproveite a leitura e aprenda muito 
                sobre as tecnologias de IA mais avançadas da atualidade.</p>
                <p>Se tiver qualquer dúvida, responda a este e-mail.</p>
                <p>Atenciosamente,<br>Equipe IA Trends</p>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(body, 'html'))

        # Anexar o PDF
        ebook_path = os.path.join(
            os.path.dirname(__file__), 
            'static', 
            'As-50-IAs-Mais-Poderosas-do-Mundo-2025.pdf'
        )

        # Se o arquivo não existir, crie um PDF de exemplo
        # (apenas para demonstração)
        if not os.path.exists(ebook_path):
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter

                # Criar diretório se não existir
                os.makedirs(os.path.dirname(ebook_path), exist_ok=True)

                pdf = canvas.Canvas(ebook_path, pagesize=letter)
                pdf.setFont("Helvetica-Bold", 24)
                pdf.drawString(72, 750, "As 50 IAs Mais Poderosas do Mundo")
                pdf.setFont("Helvetica-Bold", 20)
                pdf.drawString(72, 720, "Edição 2025")
                pdf.setFont("Helvetica", 12)
                pdf.drawString(72, 680, "Este é um e-book de demonstração.")
                pdf.save()
            except ImportError:
                print("Biblioteca reportlab não está instalada. "
                      "PDF não foi criado.")
                return False

        with open(ebook_path, "rb") as f:
            attach = MIMEApplication(f.read(), _subtype="pdf")
            attach.add_header(
                'Content-Disposition', 
                'attachment', 
                filename="As-50-IAs-Mais-Poderosas-do-Mundo-2025.pdf"
            )
            msg.attach(attach)

        # Enviar e-mail
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()

        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {str(e)}")
        return False


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)