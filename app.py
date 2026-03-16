"""
LME Reuma — Servidor Web
Compatível com Railway, Render, Fly.io e qualquer host Python.
"""
import json, os, subprocess, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
TEMPLATE   = os.path.join(BASE_DIR, "NovomodelodeLME-EDITAVEL.pdf")
FILL_SCRIPT= os.path.join(BASE_DIR, "fill_fillable_fields.py")
APP_HTML   = os.path.join(BASE_DIR, "lme-reuma.html")
PORT       = int(os.environ.get("PORT", 8765))

def gerar_pdf(data):
    MED = data.get("medico", {})
    PAC = data.get("paciente", {})
    LME = data.get("lme", {})

    qtd_map = [
        ['Text16','Text22','Text32','Text40','Text56','Text62'],
        ['Text17','Text23','Text33','Text41','Text57','Text63'],
        ['Text18','Text24','Text34','Text42','Text58','Text64'],
        ['Text19','Text25','Text35','Text43','Text59','Text65'],
        ['Text20','Text26','Text36','Text44','Text60','Text66'],
        ['Text21','Text27','Text37','Text45','Text61','Text67'],
    ]
    med_nome_map = ['Text8','Text9','Text10','Text11','Text12','Text13']

    values = [
        {"field_id":"Text1", "description":"CNES",          "page":1,"value":MED.get("cnes","")},
        {"field_id":"Text2", "description":"Estabelecimento","page":1,"value":MED.get("instituicao","")},
        {"field_id":"Text3", "description":"Nome civil",     "page":1,"value":PAC.get("nome","")},
        {"field_id":"Text6", "description":"Peso",           "page":1,"value":PAC.get("peso","")},
        {"field_id":"Text4", "description":"Nome social",    "page":1,"value":PAC.get("nomeSocial","")},
        {"field_id":"Text7", "description":"Altura",         "page":1,"value":PAC.get("altura","")},
        {"field_id":"Text5", "description":"Nome da mãe",   "page":1,"value":PAC.get("mae","")},
        {"field_id":"Text14","description":"CID-10",         "page":1,"value":LME.get("cid10","")},
        {"field_id":"Text31","description":"Diagnóstico",    "page":1,"value":LME.get("diagnostico","")},
        {"field_id":"Text15","description":"Anamnese",       "page":1,"value":LME.get("anamnese","")},
        {"field_id":"Text46","description":"Nome médico",    "page":1,"value":MED.get("nome","")},
        {"field_id":"Text47","description":"CNS médico",     "page":1,"value":MED.get("cns","")},
        {"field_id":"Text48","description":"Data",           "page":1,"value":LME.get("dataStr","")},
        {"field_id":"Button29","description":"Trat. prévio","page":1,
            "value":"/<2>" if LME.get("tratPrevioSim") else "/<1>"},
        {"field_id":"Button38","description":"Incapaz",     "page":1,
            "value":"/<2>" if LME.get("incapaz") else "/<1>"},
        {"field_id":"Button82","description":"CPF radio",   "page":1,"value":"/<1>"},
        {"field_id":"Text52", "description":"CPF",          "page":1,"value":PAC.get("cpf","")},
    ]

    if LME.get("tratPrevio",""):
        values.append({"field_id":"Text30","description":"Relato","page":1,"value":LME["tratPrevio"]})
    if LME.get("nomeResponsavel",""):
        values.append({"field_id":"Text39","description":"Responsável","page":1,"value":LME["nomeResponsavel"]})

    meds = LME.get("meds", [])
    for i in range(6):
        med = meds[i] if i < len(meds) else {"nome":"","qtd":[]}
        values.append({"field_id":med_nome_map[i],"description":f"Med{i+1}","page":1,"value":med.get("nome","")})
        qtds = med.get("qtd",["","","","","",""])
        for j, qtd_id in enumerate(qtd_map[i]):
            q = qtds[j] if j < len(qtds) else ""
            values.append({"field_id":qtd_id,"description":f"M{i+1}m{j+1}","page":1,"value":q})

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp_j:
        json.dump(values, tmp_j, ensure_ascii=False)
        tmp_j_path = tmp_j.name

    out_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    out_pdf.close()

    result = subprocess.run(
        ["python3", FILL_SCRIPT, TEMPLATE, tmp_j_path, out_pdf.name],
        capture_output=True, text=True
    )
    os.unlink(tmp_j_path)

    if result.returncode != 0:
        raise RuntimeError(result.stderr or "Erro ao gerar PDF")

    with open(out_pdf.name, 'rb') as f:
        pdf_bytes = f.read()
    os.unlink(out_pdf.name)
    return pdf_bytes


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[LME] {fmt % args}")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/index.html'):
            try:
                with open(APP_HTML, 'rb') as f:
                    body = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', len(body))
                self._cors()
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if urlparse(self.path).path != '/gerar-lme':
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            data   = json.loads(self.rfile.read(length))
            pdf    = gerar_pdf(data)
            nome   = data.get("paciente",{}).get("nome","paciente").replace(" ","_")
            fname  = f"LME_{nome}.pdf"
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition', f'attachment; filename="{fname}"')
            self.send_header('Content-Length', len(pdf))
            self._cors()
            self.end_headers()
            self.wfile.write(pdf)
        except Exception as e:
            err = str(e).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', len(err))
            self._cors()
            self.end_headers()
            self.wfile.write(err)


if __name__ == '__main__':
    print(f"LME Reuma rodando na porta {PORT}")
    HTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
