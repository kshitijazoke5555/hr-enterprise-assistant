user_schema = {
 "employee_id": str,
 "name": str,
 "password": str,
 "role": str,  # HR_ADMIN / EMPLOYEE / MANAGER
 "department": str,
}

policy_schema = {
 "policy_name": str,
 "department": str,
 "version": str,
 "effective_date": str,
 "restricted": bool
}
