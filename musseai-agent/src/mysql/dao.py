# 用户数据库操作函数
from mysql.model import UserModel


def db_get_user_by_email(db, email: str):
    """根据邮箱获取用户"""
    return db.query(UserModel).filter(UserModel.email == email).first()


def db_get_user_by_username(db, username: str):
    """根据用户名获取用户"""
    return db.query(UserModel).filter(UserModel.username == username).first()


# def db_create_user(db, user: UserRegister):
#     """创建新用户"""
#     user_id = generate_user_id_from_email(user.email)
#     hashed_password = get_password_hash(user.password)

#     db_user = UserModel(
#         user_id=user_id,
#         email=user.email,
#         username=user.username,
#         hashed_password=hashed_password,
#         full_name=user.full_name,
#         disabled=False,
#         created_at=datetime.datetime.utcnow()
#     )

#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
#     return db_user


def db_update_user_password(db, user_id: str, new_hashed_password: str):
    """更新用户密码"""
    db_user = db.query(UserModel).filter(UserModel.user_id == user_id).first()
    if db_user:
        db_user.hashed_password = new_hashed_password
        db.commit()
        return True
    return False


# 交易订单数据库操作
# def db_create_swap_order(db, order_data):
#     """创建交易订单记录"""
#     db_order = SwapOrderModel(**order_data)
#     db.add(db_order)
#     db.commit()
#     db.refresh(db_order)
#     return db_order

# def db_get_user_orders(db, from_address: str):
#     """获取用户的订单历史"""
#     return db.query(SwapOrderModel).filter(
#         SwapOrderModel.from_address == from_address
#     ).order_by(SwapOrderModel.created_at.desc()).all()
