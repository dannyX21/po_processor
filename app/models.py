from . import db
from datetime import datetime
from flask import current_app, request
from .email import send_email
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, AnonymousUserMixin, current_user
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from . import login_manager, db
import hashlib

class PO_line(db.Model):
    __tablename__ = 'po_lines'
    id = db.Column(db.Integer, primary_key=True)
    # po_number = db.Column(db.String(10), db.ForeignKey('pos.po_number'), index=True)
    po_id = db.Column(db.Integer, db.ForeignKey('pos.id'), index=True)#relationship("PO", back_populates="po_lines")
    ln = db.Column(db.Integer, default=0)
    pn = db.Column(db.String(32), nullable=True)
    serie_id = db.Column(db.Integer, db.ForeignKey('series.id'), index=True)
    #serie = db.relationship("Serie", backref="po_lines", lazy='dynamic')
    req_rev_level = db.Column(db.String(2))
    req_ship_date = db.Column(db.DateTime, nullable=False)
    req_qty = db.Column(db.Integer, default=1)
    req_unit_price = db.Column(db.Float)
    upc = db.Column(db.String(11), nullable=True, default=None)
    our_ship_date = db.Column(db.DateTime,nullable=True, default=None)
    our_rev_level = db.Column(db.String(2),nullable=True, default=None)
    our_unit_price = db.Column(db.Float, default=0)
    def __repr__(self):
        return "id: {}; PO# {}; ln: {}; pn: {}; req_rev_level: {}; req_ship_date: {}; req_qty: {};".format(self.id, self.ln, self.pn, self.req_rev_level, self.req_ship_date, self.req_qty)

class PO(db.Model):
    __tablename__ = 'pos'
    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(10), unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'),index=True)
    #customer = db.relationship("Customer", backref="pos", lazy='dynamic')
    date_received = db.Column(db.DateTime,default=datetime.utcnow)
    ship_to = db.Column(db.String(64),nullable=True, default=None)
    planner = db.Column(db.String(64),nullable=True)
    comments = db.Column(db.Text, nullable=True, default=None)
    sumbitter = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    status = db.Column(db.Integer,default=0)
    total = db.Column(db.Float,default=0)
    po_lines = db.relationship("PO_line", order_by=PO_line.ln, backref="po", lazy='dynamic')
    def __repr__(self):
        return "PO# {}; date_received: {}; ship_to: {}; planner: {}; comments: {}; csr: {}; status: {}; total: {}".format(self.po_number, self.date_received, self.ship_to, self.planner, self.comments, self.csr, self.status, self.total)

class Price(db.Model):
    __tablename__='prices'
    id=db.Column(db.Integer, primary_key=True)
    serie_id = db.Column(db.Integer, db.ForeignKey('series.id'), index=True)
    #serie = db.relationship("Serie", backref='prices', lazy='dynamic')
    length = db.Column(db.Float,nullable=False, default=1)
    price = db.Column(db.Float, nullable=False, default=0)

class Serie(db.Model):
    __tablename__='series'
    id=db.Column(db.Integer,primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'),index=True)
    customer = db.relationship("Customer", backref="series")
    prices = db.relationship("Price",order_by=Price.id, backref='serie', lazy='dynamic')
    po_lines = db.relationship("PO_line",order_by=PO_line.id, backref="serie", lazy='dynamic')
    pn_format = db.Column(db.String(64), nullable=False)
    regex = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(64),nullable=True,default=None)
    rev_level = db.Column(db.String(2),default='00')
    def __repr__(self):
        return "id: {}; customer_id: {}; customer.name: {}; pn_format: {}; regex: {}; description: {}; rev_level: {};".format(self.id, self.customer_id, self.customer.name, self.pn_format, self.regex, self.description, self.rev_level)

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(5), unique=True, nullable=False)
    name = db.Column(db.String(16), unique=True, nullable=False)
    #series = db.relationship("Serie", order_by=Serie.pn_format, backref="customer", lazy='dynamic')
    pos = db.relationship("PO", order_by=PO.po_number, backref="customer", lazy='dynamic')
    def __repr__(self):
        return "id: {}; name: {};".format(self.id, self.name)

class SNAP_pricing(db.Model):
    __tablename__ = 'snap_pricing'
    id = db.Column(db.Integer, primary_key=True)
    serie = db.Column(db.String(16),unique=True)
    regex = db.Column(db.String(160), nullable=False)
    base = db.Column(db.Float, nullable=False, default=0)
    per_ft_adder = db.Column(db.Float, nullable=False, default=0)
    rev_level = db.Column(db.String(2),nullable=False, default='00')

    def __repr__(self):
        return "id: {}, regex: {}, base_price: ${}, per ft adder: ${}.".format(self.id, self.regex, self.base, self.per_ft_adder)


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')

    @staticmethod
    def insert_roles():
        roles = {
        'User': (Permission.VIEW , True),
        'Operator': (Permission.VIEW | Permission.MODIFY, False),
        'Administrator': (0xff, False)
        }
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role %r>' % self.name


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64),unique=True, index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    name = db.Column(db.String(64))
    position = db.Column(db.String(64))
    submitted_pos = db.relationship('PO',backref='po', lazy='dynamic')
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)
    password_hash = db.Column(db.String(128))
    confirmed = db.Column(db.Boolean, default=False)
    avatar_hash = db.Column(db.String(32))
    pos = db.relationship('PO', backref='submitter', lazy='dynamic')
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute.')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'],expiration)
        return s.dumps({'confirm': self.id})

    def confirm(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True

    def can(self, permissions):
        return self.role is not None and (self.role.permissions & permissions) == permissions

    def is_administrator(self):
        return self.can(Permission.ADMINISTER)

    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)

    def gravatar(self, size=100, default='identicon', rating='g'):
        if request.is_secure:
            url = 'https://secure.gravatar.com/avatar'
        else:
            url = 'http://www.gravatar.com/avatar'
        hash = self.avatar_hash or hashlib.md5(self.email.encode('utf-8')).hexdigest()
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(url=url, hash=hash, size=size, default=default, rating=rating)

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config['TRACKER_ADMIN']:
                self.role = Role.query.filter_by(permissions=0xff).first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()

        if self.email is not None and self.avatar_hash is None:
            self.avatar_hash = hashlib.md5(self.email.encode('utf-8')).hexdigest()


    def __repr__(self):
        return '<User %r>' % self.username

class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False

class Permission:
    VIEW = 0x01
    MODIFY = 0x02
    ADMINISTER = 0x80

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

login_manager.anonymous_user = AnonymousUser
