from . import main
from .. import db
from .forms import NewCustomerForm, NewSeriesForm, FileUpload_Form
from ..models import User, Role, Permission, Customer, Serie, Price, PO, PO_line
from ..email import send_email
from flask import Flask, render_template, request, session, redirect, url_for, flash, current_app, abort, send_from_directory
from datetime import date, datetime
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from ..decorators import admin_required, permission_required
import os, time, re, sys

ALLOWED_EXTENSIONS = set(['pdf'])

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/favicon.png')
def favicon():
    return send_from_directory(os.path.join(main.root_path, 'static'), 'favicon.png')

@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        abort(404)
    return render_template('user.html',user=user)

@main.route('/edit-profile', methods=['GET','POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.position = form.position.data
        db.session.add(current_user)
        flash('Your profile has been updated.')
        return redirect(url_for('.user',username=current_user.username))
    form.name.data = current_user.name
    form.position.data = current_user.position
    return render_template('edit_profile.html', form=form)

@main.route('/edit-profile/<int:id>', methods=['GET','POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.position = form.position.data
        db.session.add(user)
        flash('The profile has been updated.')
        return redirect(url_for('.user',username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.position.data = user.position
    return render_template('edit_profile.html', form=form, user=user)

@main.route('/import_hubbell/', methods=['GET','POST'])
@login_required
@admin_required
def import_hubbell():
    form =FileUpload_Form()
    if form.validate_on_submit():
        if 'fileUpload' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['fileUpload']
        if file.filename == '':
            flash('No selected file.')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            f = convertPdf2Text(os.path.join(current_app.config['UPLOAD_FOLDER'],filename))
            process_po(f,"HUB")
            return redirect(request.url)
    return render_template('import.html', form=form)

@main.route('/new_customer/', methods=['GET','POST'])
@login_required
@admin_required
def new_customer():
    form = NewCustomerForm()
    if form.validate_on_submit():
        c = Customer(code=form.code.data, name=form.name.data)
        db.session.add(c)
        db.session.commit()
        flash("Customer '{}' has been saved.".format(c.name))
        return redirect(url_for('.view_customers'))
    else:
        return render_template('new_customer.html', form=form)

@main.route('/view_customers/', methods=['GET'])
@login_required
def view_customers():
    customers = Customer.query.order_by(Customer.name).all()
    return render_template('customers.html', customers=customers)

@main.route('/new_serie/', methods=['GET','POST'])
@login_required
@admin_required
def new_serie():
    form = NewSeriesForm()
    if form.validate_on_submit():
        s = Serie(customer_id=form.customer_id.data, pn_format=form.pn_format.data, regex=form.regex.data, description=form.description.data, rev_level=form.rev_level.data)
        db.session.add(s)
        db.session.commit()
        flash("Serie '{}' has been saved.".format(s.description))
        return redirect(url_for('.view_series'))
    else:
        return render_template('new_serie.html', form=form)

@main.route('/view_series/')
@login_required
def view_series():
    series = Serie.query.order_by(Serie.pn_format).all()
    return render_template('series.html',series=series)

@main.route('/view-prices/<int:id>', methods=['GET','POST'])
@login_required
@admin_required
def view_prices (id):
    prices = Price.query.filter_by(serie_id=id).order_by(Price.length).all()
    serie = Serie.query.filter_by(id=id).first()
    return render_template('prices.html', prices=prices, serie=serie)

@main.route('/view-order/<int:id>', methods=['GET','POST'])
@login_required
@admin_required
def view_order (id):
    order = PO.query.get_or_404(id)
    return render_template('order.html', order=order)

@main.route('/import-prices/', methods=['GET', 'POST'])
@login_required
@admin_required
def import_prices():
    form=FileUpload_Form()
    if form.validate_on_submit():
        if 'fileUpload' not in request.files:
            flash('No file found.')
            return redirect (request.url)
        file=request.files['fileUpload']
        if file.filename=='':
            flash('No file was selected.')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'],filename))

            return redirect(request.url)
    return render_template('import_prices.html', form=form)

@main.route('/unprocessed/', methods=['GET'])
@login_required
def unprocessed():
    orders = PO.query.filter_by(status=0).all()
    return render_template('orders.html', orders=orders, status=0)

@main.route('/processed/', methods=['GET'])
@login_required
def processed():
    orders = PO.query.filter_by(status=1).all()
    return render_template('orders.html', orders=orders, status=1)

@main.route('/update_line/<int:id>', methods=['POST'])
@login_required
def update_line(id):
    po_line = PO_line.query.get_or_404(id)
    our_unit_price = request.form.get('our_unit_price',0,type=float)
    req_ship_date = request.form.get('req_ship_date',0,type=str)
    po_line.our_unit_price = our_unit_price
    po_line.req_ship_date = datetime.strptime(req_ship_date,"%m%d%y").date()
    db.session.add(po_line)
    db.session.commit()
    return "ok"

@main.route('/update_order_status/<int:id>', methods=['POST'])
@login_required
def update_order_status(id):
    order = PO.query.get_or_404(id)
    new_status = request.form.get('status',0,type=int)
    print("New status: {}".format(new_status))
    order.status=new_status;
    db.session.add(order)
    db.session.commit()
    return redirect(request.url)

@main.route('/verify_price/', methods=['GET'])
@login_required
def verify_price():
    return render_template('verify_price.html')

@main.route('/verify/<pn>', methods=['POST'])
@login_required
def verify(pn):
    customer = Customer.query.filter_by(code='HUB').first()
    if customer:
        series = Serie.query.filter_by(customer_id=customer.id).filter(Serie.pn_format!='UNKNOWN').all()
        result = verify_item(pn, 'HUB', series)
        return render_template("_item_info.html", result=result,pn=pn)
    else:
        abort(404)



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def convertPdf2Text(full_path):
    os.system('./pdf2txt.sh {} {}.txt'.format(full_path, full_path))
    print("File converted: {}.txt".format(full_path))
    return full_path+'.txt'

def process_po(po_file, customer_code):
    customer = Customer.query.filter_by(code=customer_code).first()
    if customer:
        series = Serie.query.filter_by(customer_id=customer.id).filter(Serie.pn_format!='UNKNOWN').all()
        if os.path.isfile(po_file):
            f = open(po_file,'r')
            lines = f.readlines()
            f.close()
            itemregex = re.compile(r'^(?P<ln>\d{1,3}) +(?P<pn>[A-Z0-9]+)(?P<ft_term>-FT)? +(?P<desc>[\w, -]+) +(?P<ship_date>\d{2}\/\d{2}\/\d{4}) +(?P<qty>[\d.,]+) +(?P<um>[A-Z]{2}) *(?P<unit_price>[\d.]+) \/ +(?P<units>\d+) +[A-Z]{2} +(?P<ext_price>[\d.,]+) USD$')
            rev_levelregex = re.compile(r'Document Version: (?P<rev_level>\d+)$')
            poregex = re.compile(r'^ Purchase order *(?P<po_number>\d{10})')
            shiptoregex = re.compile(r'Created by: +(?P<planner>[A-Za-z ]+) +BEL FUSE INC +(?P<ship_to>[A-Za-z0-9 -.]+)$')
            totalregex = re.compile(r'TOTAL NET VALUE EXCL\. TAX USD +(?P<total>[0-9,.]+)$')
            po = PO()
            ship_to = None
            planner = None
            total = 0
            l = 0
            while po.po_number is None:
                mo  = poregex.search(lines[l])
                if mo != None:
                    po.po_number = mo.group(1)
                    po.customer_id = customer.id
                    po.date_received = datetime.today()
                    print("\nPO# {}\n".format(po.po_number))
                l += 1
            while po.planner is None:
                mo = shiptoregex.search(lines[l])
                if mo != None:
                    po.planner = mo.group(1).strip()
                    po.ship_to = mo.group(2).strip()
                    print("Planner: {}\nShip to: {}\n".format(po.planner, po.ship_to))
                l += 1
            po.sumbitter = current_user.id
            db.session.add(po)
            line = None
            for c in range(l,len(lines)):
                mo = itemregex.search(lines[c])
                if mo != None:
                    line = PO_line()
                    line.po_id = po.id
                    line.ln = int(mo.group(1))/10
                    line.pn = mo.group(2)
                    line.req_ship_date = datetime.strptime(mo.group(5),'%m/%d/%Y')
                    line.req_qty = int(float(mo.group(6).replace(',','')))
                    line.req_unit_price = float(mo.group(8))/float(mo.group(9))
                    line.our_unit_price, line.our_rev_level, line.serie = verify_item(line.pn, customer_code, series)
                    po.po_lines.append(line)
                    db.session.add(line)
                    db.session.commit()
                    continue
                mo = rev_levelregex.search(lines[c])
                if mo is not None and line is not None:
                    line.req_rev_level = mo.group(1)
                    db.session.add(line)
                    db.session.commit()
                mo = totalregex.search(lines[c])
                if mo is not None:
                    po.total = float(mo.group(1).replace(',',''))
                    db.session.add(po)
                    db.session.commit()
                    flash("PO# {} has been successfully imported.".format(po.po_number))
                    break

def verify_item(pn, customer, series):
    info = [None, None, None]
    for s in series:
        regex = re.compile(s.regex)
        mo = regex.search(pn)
        if mo is not None:
            print(s.regex)
            d = mo.groupdict()
            print(d)
            length = int(d.get('length'))
            color = d.get('color')
            print("Length: {}, Color: {}".format(length, color))
            boxqty = d.get('boxqty')
            p = Price.query.filter_by(serie_id=s.id).filter_by(length=length).first()
            info[0]=p.price
            info[1]=s.rev_level
            info[2]=s
            return info
    unknown = Serie.query.filter_by(customer_id=customer).filter(Serie.pn_format == 'UNKNOWN').first()
    info[2]=unknown
    return info
