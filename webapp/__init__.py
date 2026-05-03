"""Flask application factory."""

from flask import Flask
from flask_login import LoginManager

import db
import config

login_manager = LoginManager()


def create_app(bot=None) -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.secret_key = config.SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Store bot reference so routes can query guild membership
    app.bot = bot

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = ""  # suppress default flash

    from .auth import auth_bp, User

    @login_manager.user_loader
    def load_user(user_id: str):
        data = db.get_user(user_id)
        return User(data) if data else None

    from .views import main_bp
    from .api import api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
