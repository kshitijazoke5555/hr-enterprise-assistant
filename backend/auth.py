from .db import users_collection

def validate_user(employee_id, password):
    user = users_collection.find_one({"employee_id": employee_id, "password": password})
    return user

def check_access(user, department):
    if user["role"] == "HR_ADMIN":
        return True
    return user["department"] == department
