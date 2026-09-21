
from .admin_menu import register_admin_handlers
from .add_account import register_account_handlers
from .set_reviews import register_review_handlers
from .rotation_engine import register_rotation_handlers

def register_all_handlers(app):
    
    register_admin_handlers(app)
    register_account_handlers(app)
    register_review_handlers(app)
    register_rotation_handlers(app)