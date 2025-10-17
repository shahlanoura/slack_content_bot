import os
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
from dotenv import load_dotenv

load_dotenv()

def send_pdf_via_email(user_email, pdf_path, user_name="User"):
    """
    Send PDF report via SendGrid email
    """
    try:
        # Read PDF file
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Encode PDF for attachment
        encoded_pdf = base64.b64encode(pdf_data).decode()
        
        # Create email message
        message = Mail(
            from_email=os.getenv('SENDGRID_FROM_EMAIL'),
            to_emails=user_email,
            subject='📄 Your Content Pipeline Report is Ready!',
            html_content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: #4F46E5; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background: #f9f9f9; }}
                    .footer {{ text-align: center; padding: 20px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎯 Content Pipeline Report</h1>
                    </div>
                    <div class="content">
                        <h2>Hello {user_name}!</h2>
                        <p>Your AI-powered content pipeline analysis is complete and ready for review.</p>
                        
                        <h3>📊 What's included in your report:</h3>
                        <ul>
                            <li>✅ Cleaned and organized keywords</li>
                            <li>✅ Semantic keyword clusters</li>
                            <li>✅ Content outlines from top-ranking pages</li>
                            <li>✅ Ready-to-use post ideas</li>
                            <li>✅ Research sources and references</li>
                        </ul>
                        
                        <p><strong>📎 Attachment:</strong> Your detailed PDF report is attached to this email.</p>
                        
                        <p>Happy content creating! 🚀</p>
                    </div>
                    <div class="footer">
                        <p>Powered by AI Content Pipeline</p>
                        <p><small>This is an automated message. Please do not reply.</small></p>
                    </div>
                </div>
            </body>
            </html>
            """
        )
        
        # Add PDF attachment
        attachment = Attachment()
        attachment.file_content = FileContent(encoded_pdf)
        attachment.file_name = FileName(f"content_pipeline_report.pdf")
        attachment.file_type = FileType('application/pdf')
        attachment.disposition = Disposition('attachment')
        message.attachment = attachment
        
        # Send email
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        response = sg.send(message)
        
        print(f"✅ Email sent to {user_email} with status: {response.status_code}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False