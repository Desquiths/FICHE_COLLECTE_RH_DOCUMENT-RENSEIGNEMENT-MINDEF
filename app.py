AYT_FIELDS=["mecano","nom_gendarme","prenoms_gendarme","type_relation","second_parent","date_relation","employe_mindef","matricule_mindef","nom_lie","prenoms_lie","civilite","sexe","date_naissance","reference_document","scolarise","invalidite","personne_a_contacter","telephone","adresse"]
import json, os, sqlite3
from flask import Flask, request, render_template, redirect, url_for, send_file, session
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "data.db")
COLS_FILE = os.path.join(BASE, "columns.json")

def load_columns():
    with open(COLS_FILE, encoding="utf-8") as f:
        return json.load(f)

COLUMNS = load_columns()

app = Flask(__name__)
app.secret_key = "mindef-rh-secret"
ADMIN_USER="admin"
ADMIN_PASS="admin"

def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cols_sql = ", ".join(f'"{c}" TEXT' for c in COLUMNS)
    conn.execute(f'CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols_sql})')
from functools import wraps
def login_required(f):
    @wraps(f)
    def w(*a,**k):
        if not session.get("admin"): return redirect(url_for("login"))
        return f(*a,**k)
    return w
def col_exists(name):
    return name in COLUMNS

@app.route("/admin")
@login_required
def dashboard():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    recent = conn.execute("SELECT * FROM records ORDER BY id DESC LIMIT 8").fetchall()
    def group(col):
        if col not in COLUMNS: return []
        rows = conn.execute(f'SELECT "{col}", COUNT(*) c FROM records GROUP BY "{col}" ORDER BY c DESC LIMIT 8').fetchall()
        return [(r[col], r["c"]) for r in rows]
    by_service = group("UNITE/SERVICE")
    by_sexe = group("SEXE")
    by_grade = group("GRADE ACTUEL")
    grade_order = {"GBR":1,"CLM":2,"COL":3,"LCL":4,"CEN":5,"CNE":6,"LTN":7,"SLTN":8,"ACM":9,"ADC":10,"ADJ":11,"MDC":12,"MDL":13}
    by_grade = sorted(by_grade, key=lambda x: grade_order.get(x[0],99))
    conn.close()
    return render_template("dashboard.html", columns=COLUMNS, total=total, recent=recent,
                          by_service=by_service, by_sexe=by_sexe,
                          by_grade=by_grade)

@app.route("/records")
@login_required
def records():
    q = request.args.get("q", "").strip()
    msg = request.args.get("msg", "")
    conn = get_conn()
    if q:
        where = " OR ".join(f'"{c}" LIKE ?' for c in COLUMNS)
        params = [f"%{q}%"] * len(COLUMNS)
        rows = conn.execute(f"SELECT * FROM records WHERE {where} ORDER BY id DESC", params).fetchall()
    else:
        rows = conn.execute("SELECT * FROM records ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("records.html", columns=COLUMNS, rows=rows, q=q, msg=msg)

@app.route("/saisie")
def saisie():
    msg = request.args.get("msg","")
    return render_template("saisie.html", msg=msg)

STEPS = [
  ["MATRICULE","MECANO","TYPE DE PERSONNE","NOM","PRENOMS","CIVILITE","SITUATION DE FAMILLE","SEXE","DATE DE NAISSANCE","LIEU DE NAISSANCE","LOCALITE","PAYS DE NAISSANCE","NATIONALITE PERSONNELLE"],
  ["DATE D'ENTREE EN SERVICE","UNITE/SERVICE","LIEU DERNIERE AFFECTATION","DATE DERNIERE AFFECTATION","REFERENCE PIECE JUSTIFICATIVE DE L'AFFECTATION","DERNIER EMPLOI","DATE DERNIER EMPLOI","GRADE ACTUEL","CATEGORIE GRADE","DATE PROMOTION","REFERENCE PIECE JUSTIFICATIVE DE LA PROMOTION","ECHELON ACTUEL","DATE EFFET INDICE","SOUS-POSITION STATUTAIRE","POSITION STATUTAIRE","DATE POSITION STATUTAIRE","REFERENCE DOCUMENT JUSTIFICATIF"],
  ["REGIE","DOMAINE STRATECO-OPERATIONNEL","DOMAINE STRATEGIQUE","DOMAINE OPERATIONNEL","METIER","SPECIALITE","FILIERE PROFESSIONNELLE","ORIGINE"],
  ["NUMERO CIM","DATE EDITION CIM","DATE D'EXPIRATION CIM","N°CPC","DATE D'EDITION CPC","N°CMU","N°FPM","N°MUGEFCI","N°CNI","DATE D'EDITION CNI","N°EXTRAIT"],
  ["TAILLE (CM)","ETHNIE","GROUPE SANGUIN","COMMUNE/SOUS PREFECTURE","VILLE","ADRESSE","NUMERO TELEPHONE"],
]

@app.route("/add", methods=["GET", "POST"])
@app.route("/add/<int:step>", methods=["GET", "POST"])
def add(step=1):
    if step < 1 or step > len(STEPS):
        return redirect(url_for("add", step=1))
    if request.method == "POST":
        draft = session.get("draft", {})
        for c in STEPS[step-1]:
            draft[c] = request.form.get(c, "")
        session["draft"] = draft
        if step < len(STEPS):
            return redirect(url_for("add", step=step+1))
        # final save
        vals = [draft.get(c, "") for c in COLUMNS]
        conn = get_conn()
        eid = session.pop("edit_id", None)
        if eid:
            setsql = ", ".join(f'"{c}"=?' for c in COLUMNS)
            conn.execute(f'UPDATE records SET {setsql} WHERE id=?', vals + [eid])
        else:
            placeholders = ", ".join("?" for _ in COLUMNS)
            cols = ", ".join(f'"{c}"' for c in COLUMNS)
            conn.execute(f'INSERT INTO records ({cols}) VALUES ({placeholders})', vals)
        conn.commit()
        conn.close()
        mecano = draft.get("MATRICULE","")
        is_edit = bool(session.get("edit_id"))
        session.pop("draft", None)
        session.pop("edit_id", None)
        return redirect(url_for("saisie", msg="modifie" if is_edit else "enregistre"))
    draft = session.get("draft", {})
    RUBRIQUES = ["IDENTIFICATION PERSONNELLE","CARRIERE ET POSITION STATUTAIRE","AFFECTATION STRATEGIQUE ET OPERATIONNELLE","DOCUMENTS D'IDENTITE ET ADMINISTRATIFS","DONNEES PHYSIQUES ET PERSONNELLES COMPLEMENTAIRES"]
    return render_template("step.html", columns=STEPS[step-1], step=step, total=len(STEPS), draft=draft, rubrique=RUBRIQUES[step-1])



@app.route("/ayants", methods=["GET","POST"])
def ayants():
    mecano = request.args.get("mecano","") or request.form.get("mecano","")
    if request.method=="POST":
        vals=[request.form.get(f,"") for f in AYT_FIELDS]
        conn=get_conn()
        placeholders=", ".join("?" for _ in AYT_FIELDS)
        cols=", ".join(AYT_FIELDS)
        conn.execute(f"INSERT INTO ayants ({cols}) VALUES ({placeholders})", vals)
        conn.commit(); conn.close()
    conn=get_conn()
    rows=conn.execute("SELECT * FROM ayants WHERE mecano=? ORDER BY id",(mecano,)).fetchall() if mecano else conn.execute("SELECT * FROM ayants ORDER BY id").fetchall()
    conn.close()
    return render_template("ayants.html", mecano=mecano, rows=rows)

@app.route("/export_ayants")
def export_ayants():
    import csv, io
    mecano=request.args.get("mecano","")
    conn=get_conn()
    if mecano:
        rows=conn.execute("SELECT * FROM ayants WHERE mecano=? ORDER BY id",(mecano,)).fetchall()
    else:
        rows=conn.execute("SELECT * FROM ayants ORDER BY id").fetchall()
    conn.close()
    buf=io.StringIO()
    w=csv.writer(buf); w.writerow(AYT_FIELDS)
    for r in rows: w.writerow([r[f] if r[f] is not None else "" for f in AYT_FIELDS])
    from flask import Response
    return Response(buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition":"attachment; filename=ayants.csv"})



@app.route("/ayants/delete/<int:aid>", methods=["POST","GET"])
def ayants_delete(aid):
    conn=get_conn()
    row=conn.execute("SELECT mecano FROM ayants WHERE id=?",(aid,)).fetchone()
    mecano=row["mecano"] if row else ""
    conn.execute("DELETE FROM ayants WHERE id=?",(aid,))
    conn.commit(); conn.close()
    return redirect(url_for("ayants", mecano=mecano))



@app.route("/export_ayants_pdf")
def export_ayants_pdf():
    mecano=request.args.get("mecano","")
    conn=get_conn()
    if mecano:
        rows=conn.execute("SELECT * FROM ayants WHERE mecano=? ORDER BY id",(mecano,)).fetchall()
    else:
        rows=conn.execute("SELECT * FROM ayants ORDER BY id").fetchall()
    conn.close()
    return render_template("ayants_pdf.html", rows=rows, mecano=mecano)

@app.route("/export")
@login_required
def export():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM records ORDER BY id").fetchall()
    conn.close()
    wb = Workbook()
    ws = wb.active
    ws.title = "Export"
    header_fill = PatternFill("solid", fgColor="1F4E79")
    for j, c in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=j, value=c)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    for i, r in enumerate(rows, start=2):
        for j, c in enumerate(COLUMNS, start=1):
            ws.cell(row=i, column=j, value=r[c])
    for j in range(1, len(COLUMNS)+1):
        ws.column_dimensions[ws.cell(row=1, column=j).column_letter].width = 18
    ws.freeze_panes = "A2"
    path = os.path.join(BASE, "export.xlsx")
    wb.save(path)
    return send_file(path, as_attachment=True, download_name="export.xlsx")

@app.route("/login", methods=["GET","POST"])
def login():
    err=None
    if request.method=="POST":
        if request.form.get("user")==ADMIN_USER and request.form.get("pass")==ADMIN_PASS:
            session["admin"]=True
            return redirect(url_for("dashboard"))
        err="Identifiants invalides"
    return render_template("login.html", err=err)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("saisie"))

@app.route("/")
def home():
    return render_template("saisie.html")

@app.route("/delete/<int:rid>", methods=["POST"])
@login_required
def delete(rid):
    conn = get_conn()
    conn.execute("DELETE FROM records WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return redirect(url_for("records", msg="supprime"))

@app.route("/edit")
@login_required
def edit():
    """Affiche le formulaire de recherche."""
    q = request.args.get("q","").strip()
    if q:
        conn = get_conn()
        rows = conn.execute('SELECT * FROM records WHERE "NOM" LIKE ? OR "MATRICULE" LIKE ? ORDER BY "NOM"', (f"%{q}%", f"%{q}%")).fetchall()
        conn.close()
        return render_template("edit.html", q=q, rows=rows)
    return render_template("edit.html", q="", rows=[])

@app.route("/edit/<int:rid>")
@login_required
def edit_record(rid):
    conn = get_conn()
    r = conn.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
    conn.close()
    if not r: return redirect(url_for("records"))
    draft = {c: r[c] for c in COLUMNS}
    session["draft"] = draft
    session["edit_id"] = rid
    return redirect(url_for("add", step=1))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
