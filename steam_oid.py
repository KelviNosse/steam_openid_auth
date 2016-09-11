from os.path import dirname, join
from flask import Flask, g, redirect, session, json
from flask_sqlalchemy import SQLAlchemy
from flask_openid import OpenID
import urllib, urllib3
import re

app = Flask(__name__)
app.config.update(
    SQLALCHEMY_DATABASE_URI = 'sqlite:///users.sqlol',
    SECRET_KEY = 'API_SECRET_KEY',
    DEBUG = True,
    PORT = 5000
)

oid = OpenID(app, join(dirname(__file__), 'openid_store'))
db = SQLAlchemy(app)
temp_avatar = ""

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    steam_id = db.Column(db.String(40))
    nickname = db.Column(db.String(80))

    @staticmethod
    def get_or_create(steam_id):
        rv = User.query.filter_by(steam_id=steam_id).first()
        if rv is None:
            rv = User()
            rv.steam_id = steam_id
            db.session.add(rv)
        return rv


_steam_id_re = re.compile('steamcommunity.com/openid/id/(.*?)$')

def get_steam_userinfo(steam_id):
    options = {
        'key': app.secret_key,
        'steamids': steam_id
    }
    url = 'http://api.steampowered.com/ISteamUser/' \
          'GetPlayerSummaries/v0001/?%s' % urllib.parse.urlencode(options)
    rv = json.load(urllib.request.urlopen(url))
    return rv['response']['players']['player'][0] or {}

@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = User.query.filter_by(id=session['user_id']).first()

@app.route("/login")
@oid.loginhandler
def login():
    if g.user is not None:
        return redirect(oid.get_next_url())
    else:
        return oid.try_login("http://steamcommunity.com/openid")

@oid.after_login
def new_user(resp):
    match = _steam_id_re.search(resp.identity_url)
    g.user = User.get_or_create(match.group(1))
    steamdata = get_steam_userinfo(g.user.steam_id)
    g.user.nickname = steamdata['personaname']
    temp_avatar = steamdata['avatar'];
    db.session.commit()
    session['user_id'] = g.user.id
    return redirect(oid.get_next_url())

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(oid.get_next_url())

@app.route('/')
def hello():
    if g.user:
        temp_avatar = get_steam_userinfo(g.user.steam_id)
        return "<div style='text-align:center;'><img src='%s' /><br> <h2>Hi, %s with Steam Id %s<br><a href='/logout'>LogOut</a></h2></div>" % (temp_avatar['avatarmedium'],g.user.nickname, g.user.steam_id)
    else:
        return "<div style='text-align:center;'><h2>You are not logged in <br><a href='/login'>LogIn</a></h2>"

if __name__ == "__main__":
    app.run()
