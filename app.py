import os, uuid, re, requests
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, abort, Response
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# ── All hardcoded config ──────────────────────────────────────────────────────
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=1)

SITE_NAME    = "TezKhabar"
SITE_TAGLINE = "Breaking News · 24/7"
SITE_URL     = "https://tezkhabar-india.onrender.com"
LOGO_URL     = "https://cdn.postimage.me/2026/06/26/56970.jpg"
GOOGLE_VERIFICATION  = "g45Udug4GCB-Ra_KHG80vOV4zsc1bwbVby7RrmtZRFk"
ADSENSE_PUB          = "ca-pub-8228784571140150"
AD_SLOT_HEADER       = "1111111111"
AD_SLOT_SIDEBAR      = "2222222222"
AD_SLOT_ARTICLE      = "3333333333"
AD_SLOT_FOOTER       = "4444444444"
ADSENSE_ENABLED      = True
CATEGORIES           = ["Politics","Sports","Business","Technology","Entertainment","World","Health","Science","Rashifal"]
ARTICLES_PER_PAGE    = 12
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)

# ── Super Admin credentials (set in Render ENV) ──────────────────────────────
SUPER_ADMIN_EMAIL    = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@tezkhabar.com")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "ChangeMe@2026!")

# ── Firebase init — only FIREBASE_PRIVATE_KEY needed as Render ENV var ───────
db = None
_raw_key = os.environ.get("FIREBASE_PRIVATE_KEY", "")
if _raw_key:
    _pk = _raw_key.strip().strip('"').strip("'")
    _pk = _pk.replace('\\n', '\n')  # double-escaped -> single newline
    _pk = _pk.replace('\n', '\n')    # literal \n -> actual newline
    _sa = {
        "type": "service_account",
        "project_id": "dreamdrop-3ca3d",
        "private_key_id": "b364bece0e98250c0da8b337c9fab14916595fdb",
        "private_key": _pk,
        "client_email": "firebase-adminsdk-fbsvc@dreamdrop-3ca3d.iam.gserviceaccount.com",
        "client_id": "105131584333538157101",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40dreamdrop-3ca3d.iam.gserviceaccount.com",
        "universe_domain": "googleapis.com"
    }
    try:
        cred = credentials.Certificate(_sa)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase connected!")
    except Exception as e:
        print(f"Firebase init failed: {e}")
        db = None
else:
    print("WARNING: FIREBASE_PRIVATE_KEY not set.")

# ── Utilities ─────────────────────────────────────────────────────────────────
def slugify(t):
    t = re.sub(r"[^\w\s-]","",t.lower().strip())
    return re.sub(r"[\s_-]+","-",t)

def hash_pw(pw):
    import hashlib
    return hashlib.sha256(pw.encode()).hexdigest()

def time_ago(dt):
    if not dt: return ""
    try:
        diff = datetime.utcnow() - dt.replace(tzinfo=None)
        s = int(diff.total_seconds())
        if s<60: return f"{s} sec pehle"
        if s<3600: return f"{s//60} min pehle"
        if s<86400: return f"{s//3600} ghante pehle"
        return f"{s//86400} din pehle"
    except: return str(dt)

def get_settings():
    if not db: return {"breaking_news":"TezKhabar pe aapka swagat hai!","maintenance_mode":False,"announcement":"","user_comments_enabled":False}
    try:
        doc = db.collection("settings").document("site").get()
        d = {"breaking_news":"TezKhabar pe aapka swagat hai!","maintenance_mode":False,"announcement":"","user_comments_enabled":False}
        return {**d,**(doc.to_dict() if doc.exists else {})}
    except: return {"breaking_news":"TezKhabar pe aapka swagat hai!","maintenance_mode":False,"announcement":"","user_comments_enabled":False}

def upload_image(data, fname):
    if not db: return ""
    try:
        apis = [a.to_dict() for a in db.collection("image_apis").where("enabled","==",True).stream()]
    except: apis=[]
    for api in sorted(apis, key=lambda x:x.get("priority",99)):
        try:
            if api.get("type")=="imgbb":
                r=requests.post("https://api.imgbb.com/1/upload",data={"key":api["key"]},files={"image":(fname,data,"image/jpeg")},timeout=15)
                if r.status_code==200: return r.json()["data"]["url"]
            elif api.get("type")=="postimage":
                r=requests.post("https://postimages.org/json/rr",data={"token":api["key"],"content":"json"},files={"file":(fname,data,"image/jpeg")},timeout=15)
                if r.status_code==200: return r.json().get("url","")
        except: continue
    return ""

# ── Auth decorators ───────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def d(*a,**k):
        if not session.get("admin_logged_in"): return redirect(url_for("admin_login"))
        return f(*a,**k)
    return d

def superadmin_required(f):
    @wraps(f)
    def d(*a,**k):
        if not session.get("admin_logged_in"): return redirect(url_for("admin_login"))
        if session.get("admin_role")!="superadmin": abort(403)
        return f(*a,**k)
    return d

def admin_required(f):
    @wraps(f)
    def d(*a,**k):
        if not session.get("admin_logged_in"): return redirect(url_for("admin_login"))
        if session.get("admin_role") not in ["admin","superadmin"]: abort(403)
        return f(*a,**k)
    return d

# ── Context processors ────────────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    s=get_settings()
    return dict(site_name=SITE_NAME,site_tagline=SITE_TAGLINE,logo_url=LOGO_URL,
                adsense_pub=ADSENSE_PUB,adsense_enabled=ADSENSE_ENABLED,
                ad_slot_header=AD_SLOT_HEADER,ad_slot_sidebar=AD_SLOT_SIDEBAR,
                ad_slot_in_article=AD_SLOT_ARTICLE,ad_slot_footer=AD_SLOT_FOOTER,
                google_verification=GOOGLE_VERIFICATION,settings=s,
                now=datetime.utcnow(),time_ago=time_ago,all_categories=CATEGORIES,
                site_url=request.url_root.rstrip("/"),is_superadmin=(session.get("admin_role")=="superadmin"),
                is_admin=(session.get("admin_role") in ["admin","superadmin"]))

# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    s=get_settings()
    if s.get("maintenance_mode") and not session.get("admin_logged_in"):
        return render_template("maintenance.html")
    arts=[]
    if db:
        try:
            arts=[{"id":d.id,**d.to_dict()} for d in db.collection("articles")
                  .where("status","==","published")
                  .order_by("published_at",direction=firestore.Query.DESCENDING).limit(30).stream()]
        except: pass
    hero=arts[0] if arts else None
    top_stories=arts[1:7]
    by_cat={c:[a for a in arts if a.get("category")==c][:4] for c in CATEGORIES[:6]}
    trending=sorted(arts,key=lambda x:x.get("views",0),reverse=True)[:5]
    picks=[a for a in arts if a.get("editors_pick")][:3]
    return render_template("index.html",hero=hero,top_stories=top_stories,by_category=by_cat,trending=trending,editors_pick=picks)

@app.route("/article/<slug>")
def article(slug):
    if not db: abort(404)
    docs=list(db.collection("articles").where("slug","==",slug).limit(1).stream())
    if not docs: abort(404)
    doc=docs[0]
    if doc.to_dict().get("status") != "published": abort(404)
    art={"id":doc.id,**doc.to_dict()}
    try: db.collection("articles").document(doc.id).update({"views":firestore.Increment(1)})
    except: pass
    art["views"]=(art.get("views") or 0)+1
    related=[]
    try:
        related=[{"id":r.id,**r.to_dict()} for r in db.collection("articles")
                 .where("category","==",art.get("category","")).limit(6).stream()
                 if r.id!=doc.id and r.to_dict().get("status")=="published"][:4]
    except: pass
    comments=[]
    if get_settings().get("user_comments_enabled"):
        try:
            comments=[{"id":c.id,**c.to_dict()} for c in db.collection("articles")
                      .document(doc.id).collection("comments").where("approved","==",True)
                      .order_by("created_at",direction=firestore.Query.DESCENDING).stream()]
        except: pass
    return render_template("article.html",article=art,related=related,comments=comments)

@app.route("/category/<name>")
def category(name):
    page=int(request.args.get("page",1))
    arts=[]
    if db:
        try:
            arts=[{"id":d.id,**d.to_dict()} for d in db.collection("articles")
                  .where("category","==",name).where("status","==","published")
                  .order_by("published_at",direction=firestore.Query.DESCENDING).stream()]
        except: pass
    paged=arts[(page-1)*ARTICLES_PER_PAGE:page*ARTICLES_PER_PAGE]
    trending=sorted(arts,key=lambda x:x.get("views",0),reverse=True)[:5]
    return render_template("category.html",articles=paged,category=name,page=page,
                           has_next=page*ARTICLES_PER_PAGE<len(arts),trending=trending)

@app.route("/tag/<tag>")
def tag_page(tag):
    arts=[]
    if db:
        try:
            arts=[{"id":d.id,**d.to_dict()} for d in db.collection("articles")
                  .where("status","==","published").order_by("published_at",direction=firestore.Query.DESCENDING).stream()
                  if tag.lower() in [t.lower() for t in d.to_dict().get("tags",[])]]
        except: pass
    return render_template("tag.html",articles=arts,tag=tag)

@app.route("/author/<author_id>")
def author_page(author_id):
    if not db: abort(404)
    doc=db.collection("users").document(author_id).get()
    if not doc.exists: abort(404)
    arts=[]
    try:
        for d in db.collection("articles").where("author_id","==",author_id).stream():
            a={"id":d.id,**d.to_dict()}
            if a.get("status")=="published": arts.append(a)
        arts.sort(key=lambda x: x.get("published_at") or _EPOCH, reverse=True)
    except: pass
    return render_template("author.html",author={"id":doc.id,**doc.to_dict()},articles=arts)

@app.route("/search")
def search():
    q=request.args.get("q","").strip(); cat=request.args.get("cat",""); results=[]
    if q and db:
        try: db.collection("search_logs").add({"query":q,"created_at":datetime.utcnow()})
        except: pass
        try:
            ql=q.lower()
            for d in db.collection("articles").where("status","==","published").stream():
                a={"id":d.id,**d.to_dict()}
                if ql in a.get("title","").lower() or ql in a.get("summary","").lower():
                    if not cat or a.get("category")==cat: results.append(a)
        except: pass
    return render_template("search.html",results=results,query=q,cat=cat)

@app.route("/on-this-day")
def on_this_day():
    today=datetime.utcnow(); arts=[]
    if db:
        try:
            for d in db.collection("articles").where("status","==","published").stream():
                a={"id":d.id,**d.to_dict()}; pub=a.get("published_at")
                if pub and hasattr(pub,"month") and pub.month==today.month and pub.day==today.day and pub.year<today.year:
                    arts.append(a)
        except: pass
    return render_template("on_this_day.html",articles=arts,today=today)

@app.route("/article/<article_id>/comment",methods=["POST"])
def post_comment(article_id):
    if not get_settings().get("user_comments_enabled"): abort(403)
    name=request.form.get("name","").strip(); text=request.form.get("text","").strip()
    if not name or not text or len(text)>1000: abort(400)
    if db: db.collection("articles").document(article_id).collection("comments").add(
        {"name":name,"text":text,"approved":False,"created_at":datetime.utcnow()})
    flash("Comment submit hua! Review ke baad show hoga.","success")
    return redirect(request.referrer or url_for("index"))

@app.route("/article/<article_id>/react",methods=["POST"])
def react(article_id):
    data = request.json or {}
    r = data.get("reaction", "")
    if r not in ["like","angry","sad","shocked"]: return jsonify({"error":"Invalid"}),400
    if db: db.collection("articles").document(article_id).update({f"reactions.{r}":firestore.Increment(1)})
    return jsonify({"ok":True})

@app.route("/about")
def about():
    return render_template("static_page.html", title="About Us", content_key="about")
@app.route("/contact")
def contact():
    return render_template("static_page.html", title="Contact Us", content_key="contact")
@app.route("/privacy")
def privacy():
    return render_template("static_page.html", title="Privacy Policy", content_key="privacy")
@app.route("/terms")
def terms():
    return render_template("static_page.html", title="Terms of Service", content_key="terms")
@app.route("/disclaimer")
def disclaimer():
    return render_template("static_page.html", title="Disclaimer", content_key="disclaimer")

@app.route("/sitemap.xml")
def sitemap():
    arts=[]
    try:
        if db:
            arts=[{"id":d.id,**d.to_dict()} for d in db.collection("articles").where("status","==","published").stream()]
    except: pass
    return Response(render_template("sitemap.xml",articles=arts,site_url=request.url_root.rstrip("/")),mimetype="application/xml")

@app.route("/rss.xml")
def rss():
    arts=[]
    try:
        if db:
            for d in db.collection("articles").where("status","==","published").stream():
                arts.append({"id":d.id,**d.to_dict()})
            arts.sort(key=lambda x: x.get("published_at") or _EPOCH, reverse=True)
            arts=arts[:20]
    except: pass
    return Response(render_template("rss.xml",articles=arts,site_url=request.url_root.rstrip("/")),mimetype="application/rss+xml")

@app.route("/robots.txt")
def robots(): return Response(f"User-agent: *\nAllow: /\nDisallow: /admin/\nSitemap: {SITE_URL}/sitemap.xml",mimetype="text/plain")

# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE LOGIN — /admin/login (Super Admin + Admin + Editor all use this)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/ads.txt")
def ads_txt(): return Response("google.com, pub-8228784571140150, DIRECT, f08c47fec0942fa0", mimetype="text/plain")

@app.route("/google798ad8a58d695c67.html")
def google_verify(): return Response("google-site-verification: google798ad8a58d695c67.html", mimetype="text/html")

@app.route("/admin/login",methods=["GET","POST"])
def admin_login():
    if session.get("admin_logged_in"): return redirect(url_for("admin_dashboard"))
    error=None
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        pw=request.form.get("password","")
        # 1. Super Admin check (ENV vars)
        if email==SUPER_ADMIN_EMAIL.lower() and pw==SUPER_ADMIN_PASSWORD:
            session.permanent=True
            session.update({"admin_logged_in":True,"admin_id":"superadmin",
                            "admin_name":"Super Admin","admin_role":"superadmin","admin_email":email})
            return redirect(url_for("admin_dashboard"))
        # 2. Firestore admin/editor check
        if db:
            try:
                docs=list(db.collection("users").where("email","==",email).where("role","in",["admin","editor"]).limit(1).stream())
                if docs:
                    u=docs[0].to_dict()
                    if u.get("password")==hash_pw(pw):
                        session.permanent=True
                        session.update({"admin_logged_in":True,"admin_id":docs[0].id,
                                        "admin_name":u.get("name","Admin"),"admin_role":u.get("role","editor"),"admin_email":email})
                        return redirect(url_for("admin_dashboard"))
            except Exception as e: print(e)
        error="Galat email ya password."
    return render_template("admin_login.html",error=error)

@app.route("/admin/logout")
def admin_logout(): session.clear(); return redirect(url_for("admin_login"))

@app.route("/invite/<token>",methods=["GET","POST"])
def accept_invite(token):
    if not db: abort(404)
    doc=db.collection("invites").document(token).get()
    if not doc.exists: abort(404)
    inv=doc.to_dict()
    if inv.get("used"): return render_template("invite.html",error="Link pehle use ho chuka hai.")
    try:
        _exp=inv.get("expires_at")
        if _exp and datetime.utcnow()>_exp.replace(tzinfo=None):
            return render_template("invite.html",error="Link expire ho gaya. Naya invite maango.")
    except: pass
    if request.method=="POST":
        name=request.form.get("name","").strip(); pw=request.form.get("password",""); confirm=request.form.get("confirm","")
        if not name or not pw or pw!=confirm:
            return render_template("invite.html",invite=inv,token=token,error="Sab fields sahi bharo.")
        db.collection("users").document(str(uuid.uuid4())).set({
            "name":name,"email":inv["email"],"role":inv["role"],"password":hash_pw(pw),
            "profile_pic":"","bio":"","designation":"","created_at":datetime.utcnow(),"invited_by":inv.get("created_by","")
        })
        db.collection("invites").document(token).update({"used":True})
        flash("Account ban gaya! Login karo.","success"); return redirect(url_for("admin_login"))
    return render_template("invite.html",invite=inv,token=token)

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/admin/")
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if not db: return render_template("admin_dashboard.html",articles_count=0,published=0,users_count=0,total_views=0,recent=[])
    arts=list(db.collection("articles").stream())
    pub=len([a for a in arts if a.to_dict().get("status")=="published"])
    recent_docs=list(db.collection("articles").order_by("created_at",direction=firestore.Query.DESCENDING).limit(10).stream())
    recent=[{"id":d.id,**d.to_dict()} for d in recent_docs]
    total_views=sum(a.get("views",0) for a in recent)
    return render_template("admin_dashboard.html",articles_count=len(arts),published=pub,
                           users_count=len(list(db.collection("users").stream())),
                           total_views=total_views,recent=recent)

@app.route("/admin/articles")
@login_required
def admin_articles():
    if not db: return render_template("admin_articles.html",articles=[],status_filter="")
    sf=request.args.get("status","")
    if sf: docs=db.collection("articles").where("status","==",sf).order_by("created_at",direction=firestore.Query.DESCENDING).stream()
    else: docs=db.collection("articles").order_by("created_at",direction=firestore.Query.DESCENDING).stream()
    return render_template("admin_articles.html",articles=[{"id":d.id,**d.to_dict()} for d in docs],status_filter=sf)

@app.route("/admin/article/new",methods=["GET","POST"])
@login_required
def admin_new_article():
    if request.method=="POST":
        title=request.form.get("title","").strip(); content=request.form.get("content","").strip()
        summary=request.form.get("summary","").strip(); category=request.form.get("category","")
        tags=[t.strip() for t in request.form.get("tags","").split(",") if t.strip()]
        status=request.form.get("status","draft"); editors_pick="editors_pick" in request.form
        image_url=request.form.get("image_url","").strip()
        if not image_url and "image" in request.files:
            f=request.files["image"]
            if f and f.filename: image_url=upload_image(f.read(),f.filename)
        slug=slugify(title)
        if db and list(db.collection("articles").where("slug","==",slug).limit(1).stream()): slug+="-"+str(uuid.uuid4())[:6]
        if db: db.collection("articles").add({
            "title":title,"content":content,"summary":summary,"category":category,"tags":tags,
            "status":status,"slug":slug,"image_url":image_url,
            "author_id":session.get("admin_id"),"author_name":session.get("admin_name"),
            "editors_pick":editors_pick,"views":0,"reactions":{"like":0,"angry":0,"sad":0,"shocked":0},
            "created_at":datetime.utcnow(),"published_at":datetime.utcnow() if status=="published" else None})
        flash("Article save ho gaya!","success"); return redirect(url_for("admin_articles"))
    return render_template("admin_new_article.html",article=None,categories=CATEGORIES)

@app.route("/admin/article/<aid>/edit",methods=["GET","POST"])
@login_required
def admin_edit_article(aid):
    if not db: abort(404)
    doc=db.collection("articles").document(aid).get()
    if not doc.exists: abort(404)
    art={"id":doc.id,**doc.to_dict()}
    if request.method=="POST":
        title=request.form.get("title","").strip(); content=request.form.get("content","").strip()
        summary=request.form.get("summary","").strip(); category=request.form.get("category","")
        tags=[t.strip() for t in request.form.get("tags","").split(",") if t.strip()]
        status=request.form.get("status",art.get("status","draft")); editors_pick="editors_pick" in request.form
        image_url=request.form.get("image_url",art.get("image_url","")).strip()
        if "image" in request.files:
            f=request.files["image"]
            if f and f.filename:
                nu=upload_image(f.read(),f.filename)
                if nu: image_url=nu
        upd={"title":title,"content":content,"summary":summary,"category":category,"tags":tags,
             "status":status,"image_url":image_url,"editors_pick":editors_pick,"updated_at":datetime.utcnow()}
        if status=="published" and not art.get("published_at"): upd["published_at"]=datetime.utcnow()
        db.collection("articles").document(aid).update(upd)
        flash("Article update ho gaya!","success"); return redirect(url_for("admin_articles"))
    art["tags_str"]=", ".join(art.get("tags",[])); return render_template("admin_new_article.html",article=art,categories=CATEGORIES)

@app.route("/admin/article/<aid>/delete",methods=["POST"])
@login_required
def admin_delete_article(aid):
    if db: db.collection("articles").document(aid).delete()
    flash("Article delete ho gaya.","info"); return redirect(url_for("admin_articles"))

@app.route("/admin/upload-image",methods=["POST"])
@login_required
def admin_upload_image():
    if "image" not in request.files: return jsonify({"error":"No file"}),400
    f=request.files["image"]; url=upload_image(f.read(),f.filename)
    return jsonify({"url":url}) if url else (jsonify({"error":"Upload failed. Add image API keys."}),500)

@app.route("/admin/categories",methods=["GET","POST"])
@login_required
def admin_categories():
    if request.method=="POST":
        name=request.form.get("name","").strip()
        if name and db: db.collection("categories").add({"name":name,"created_at":datetime.utcnow()})
        flash(f"Category add ho gayi.","success"); return redirect(url_for("admin_categories"))
    cats=[{"id":d.id,**d.to_dict()} for d in (db.collection("categories").stream() if db else [])]
    return render_template("admin_categories.html",categories=cats,default_cats=CATEGORIES)

@app.route("/admin/image-apis",methods=["GET","POST"])
@admin_required
def admin_image_apis():
    if request.method=="POST":
        action=request.form.get("action")
        if action=="add" and db:
            db.collection("image_apis").add({"name":request.form.get("name",""),"type":request.form.get("type","imgbb"),
                "key":request.form.get("key",""),"enabled":True,"priority":99,"added_at":datetime.utcnow()})
            flash("API key add ho gaya!","success")
        elif action=="toggle" and db:
            did=request.form.get("doc_id"); d=db.collection("image_apis").document(did).get()
            if d.exists: db.collection("image_apis").document(did).update({"enabled":not d.to_dict().get("enabled",True)})
        elif action=="delete" and db:
            db.collection("image_apis").document(request.form.get("doc_id")).delete(); flash("API key remove ho gayi.","info")
        return redirect(url_for("admin_image_apis"))
    apis=[{"id":d.id,**d.to_dict()} for d in (db.collection("image_apis").stream() if db else [])]
    return render_template("admin_image_apis.html",apis=apis)

@app.route("/admin/team")
@admin_required
def admin_team():
    users=[{"id":d.id,**d.to_dict()} for d in (db.collection("users").stream() if db else [])]
    invites=[{"id":d.id,**d.to_dict()} for d in (db.collection("invites").where("used","==",False).stream() if db else [])]
    return render_template("admin_team.html",users=users,invites=invites)

@app.route("/admin/invite",methods=["POST"])
@admin_required
def admin_invite():
    email=request.form.get("email","").strip().lower(); role=request.form.get("role","editor")
    if session.get("admin_role")=="admin" and role in ["admin","superadmin"]: role="editor"
    token=str(uuid.uuid4())
    if db: db.collection("invites").document(token).set({"email":email,"role":role,"used":False,
        "created_by":session.get("admin_email",""),"created_at":datetime.utcnow(),"expires_at":datetime.utcnow()+timedelta(hours=48)})
    link=url_for("accept_invite",token=token,_external=True)
    flash(f"Invite link (48hr valid): {link}","success"); return redirect(url_for("admin_team"))

@app.route("/admin/profile",methods=["GET","POST"])
@login_required
def admin_profile():
    if session.get("admin_role")=="superadmin":
        flash("Super Admin ka profile ENV se manage hota hai.","info"); return redirect(url_for("admin_dashboard"))
    if not db: abort(404)
    doc=db.collection("users").document(session["admin_id"]).get()
    if not doc.exists: abort(404)
    user={"id":doc.id,**doc.to_dict()}
    if request.method=="POST":
        pic_url=user.get("profile_pic","")
        if "profile_pic" in request.files:
            f=request.files["profile_pic"]
            if f and f.filename: nu=upload_image(f.read(),f.filename); pic_url=nu if nu else pic_url
        upd={"name":request.form.get("name","").strip(),"bio":request.form.get("bio","").strip(),
             "designation":request.form.get("designation","").strip(),"profile_pic":pic_url}
        old=request.form.get("old_password",""); new=request.form.get("new_password","")
        if old and new:
            if user.get("password")==hash_pw(old): upd["password"]=hash_pw(new); flash("Password update ho gaya.","success")
            else: flash("Purana password galat hai.","danger")
        db.collection("users").document(session["admin_id"]).update(upd)
        session["admin_name"]=upd["name"]; flash("Profile update ho gayi!","success"); return redirect(url_for("admin_profile"))
    return render_template("admin_profile.html",user=user)

@app.route("/admin/analytics")
@login_required
def admin_analytics():
    top=[{"id":d.id,**d.to_dict()} for d in (db.collection("articles").where("status","==","published")
         .order_by("views",direction=firestore.Query.DESCENDING).limit(10).stream() if db else [])]
    searches={}
    if db:
        for s in db.collection("search_logs").order_by("created_at",direction=firestore.Query.DESCENDING).limit(200).stream():
            q=s.to_dict().get("query","")
            if q: searches[q]=searches.get(q,0)+1
    return render_template("admin_analytics.html",top_articles=top,top_searches=sorted(searches.items(),key=lambda x:x[1],reverse=True)[:10])

@app.route("/admin/comments")
@login_required
def admin_comments():
    all_c=[]
    if db:
        for art in db.collection("articles").stream():
            for c in db.collection("articles").document(art.id).collection("comments").where("approved","==",False).stream():
                all_c.append({"article_id":art.id,"article_title":art.to_dict().get("title",""),"id":c.id,**c.to_dict()})
    return render_template("admin_comments.html",comments=all_c)

@app.route("/admin/comment/<aid>/<cid>/approve",methods=["POST"])
@login_required
def approve_comment(aid,cid):
    if db: db.collection("articles").document(aid).collection("comments").document(cid).update({"approved":True})
    flash("Comment approve ho gaya.","success"); return redirect(url_for("admin_comments"))

@app.route("/admin/comment/<aid>/<cid>/delete",methods=["POST"])
@login_required
def delete_comment(aid,cid):
    if db: db.collection("articles").document(aid).collection("comments").document(cid).delete()
    flash("Comment delete ho gaya.","info"); return redirect(url_for("admin_comments"))

@app.route("/admin/settings",methods=["GET","POST"])
@superadmin_required
def admin_settings():
    if request.method=="POST":
        if db: db.collection("settings").document("site").set({
            "user_comments_enabled":"user_comments" in request.form,
            "maintenance_mode":"maintenance_mode" in request.form,
            "announcement":request.form.get("announcement","").strip(),
            "breaking_news":request.form.get("breaking_news","").strip(),
            "updated_at":datetime.utcnow()},merge=True)
        flash("Settings save ho gayi!","success"); return redirect(url_for("admin_settings"))
    users=[{"id":d.id,**d.to_dict()} for d in (db.collection("users").stream() if db else [])]
    invites=[{"id":d.id,**d.to_dict()} for d in (db.collection("invites").stream() if db else [])]
    return render_template("superadmin_dashboard.html",settings=get_settings(),users=users,invites=invites,
                           articles_count=len(list(db.collection("articles").stream())) if db else 0,
                           users_count=len(users))

@app.route("/admin/remove-user/<uid>",methods=["POST"])
@superadmin_required
def admin_remove_user(uid):
    if db: db.collection("users").document(uid).delete()
    flash("User remove ho gaya.","info"); return redirect(url_for("admin_settings"))

# ── API ───────────────────────────────────────────────────────────────────────
@app.route("/api/articles")
def api_articles():
    if not db: return jsonify({"articles":[],"count":0})
    lim=min(int(request.args.get("limit",20)),50); cat=request.args.get("category","")
    if cat: docs=db.collection("articles").where("category","==",cat).where("status","==","published").order_by("published_at",direction=firestore.Query.DESCENDING).limit(lim).stream()
    else: docs=db.collection("articles").where("status","==","published").order_by("published_at",direction=firestore.Query.DESCENDING).limit(lim).stream()
    return jsonify({"articles":[{"id":d.id,"title":d.to_dict().get("title"),"slug":d.to_dict().get("slug"),"category":d.to_dict().get("category"),"image_url":d.to_dict().get("image_url"),"summary":d.to_dict().get("summary"),"views":d.to_dict().get("views",0),"published_at":str(d.to_dict().get("published_at",""))} for d in docs]})

@app.route("/api/articles/<slug>")
def api_article(slug):
    if not db: return jsonify({"error":"Not found"}),404
    docs=list(db.collection("articles").where("slug","==",slug).where("status","==","published").limit(1).stream())
    if not docs: return jsonify({"error":"Not found"}),404
    a=docs[0].to_dict(); return jsonify({"id":docs[0].id,"title":a.get("title"),"content":a.get("content"),"category":a.get("category"),"image_url":a.get("image_url"),"author_name":a.get("author_name"),"views":a.get("views",0),"tags":a.get("tags",[])})

@app.route("/api/trending")
def api_trending():
    if not db: return jsonify({"trending":[]})
    docs=db.collection("articles").where("status","==","published").order_by("views",direction=firestore.Query.DESCENDING).limit(10).stream()
    return jsonify({"trending":[{"id":d.id,"title":d.to_dict().get("title"),"slug":d.to_dict().get("slug"),"views":d.to_dict().get("views",0)} for d in docs]})

@app.route("/api/search")
def api_search():
    if not db: return jsonify({"results":[]})
    q=request.args.get("q","").strip().lower()
    if not q: return jsonify({"results":[]})
    docs=db.collection("articles").where("status","==","published").order_by("published_at",direction=firestore.Query.DESCENDING).limit(100).stream()
    return jsonify({"results":[{"id":d.id,"title":d.to_dict().get("title"),"slug":d.to_dict().get("slug"),"category":d.to_dict().get("category")} for d in docs if q in d.to_dict().get("title","").lower()][:10]})

@app.route("/api/breaking")
def api_breaking(): return jsonify({"breaking":get_settings().get("breaking_news","")})

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404
@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500
@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)

# ═══════════════════════════════════════════════════════════════════════════════
# FIREBASE SETUP GUIDE:
# 1. Firebase Console → Project Settings → Service Accounts → Generate New Private Key
# 2. Download the JSON file
# 3. Copy values from that JSON into FIREBASE_SA dict above:
#    - project_id
#    - private_key_id
#    - private_key (full key with \n)
#    - client_email
#    - client_id
#    - client_x509_cert_url
# ═══════════════════════════════════════════════════════════════════════════════
