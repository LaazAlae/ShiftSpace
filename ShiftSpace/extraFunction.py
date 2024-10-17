def validate_password(password):
    if len(password) < 8:
        print("Report: Length issue\n")
        return False
    check_lower = "abcdefghijklmnopqrstuvwxyz"
    for e in check_lower:
        if e in password:
            break
    else:
        print("Report: Missing Lower")
        return False
    
    check_Upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for e in check_Upper:
        if e in password:
            break
    else:
        print("Report: Missing Upper\n")
        return False
    
    check_number = "1234567890"
    for e in password:
        if e in check_number:
            break
    else:
        print("Report: Missing Number\n")
        return False
    
    check_special = "!@#$%^&()_-="
    for e in password:
        if e in check_special:
            break
    else:
        print("Report: Missing Special\n")
        return False

    list = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890!@#$%^&()_-="
    for e in password:
        if e not in list:
            print("Report: Including Invaild Char\n")
            return False
    print("Passed")
    return True