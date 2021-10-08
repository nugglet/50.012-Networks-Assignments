import json
from operator import itemgetter
from os import error
from PIL import Image
from io import BytesIO

from fastapi import FastAPI, Response, Depends, Request
from typing import Optional
from fastapi.param_functions import File
from pydantic import BaseModel
import redis


app = FastAPI()
r = redis.Redis(host="redis")

login = False
login_id = "admin"
login_pass = "ihavegodpowers"
wipe_key = "cleardb"


students = [
    {
        "name": "Alice",
        "id": "1004803",
        "password": "apple",
        "assignment": "HW1",
        "gpa": 4.2
    },
    {
        "name": "Bob",
        "id": "1004529",
        "password": "pear",
        "assignment": "HW1"
    },
    {
        "name": "Charlie",
        "id": "1004910",
        "password": "banana",
        "gpa": 5.0
    },
    {
        "name": "Elly",
        "id": "1004802",
        "password": "papaya",
        "assignment": "HW1",
        "gpa": 3.0
    },
    {
        "name": "Ferdinand",
        "id": "1009999",
        "password": "vonAegir",
        "assignment": "HW1",
        "gpa": 5.0
    }
]


class Student(BaseModel):
    name: str
    id: str
    password: str
    gpa: Optional[int] = None
    assignment: Optional[int] = None
    # photo: Optional[bytes] = None


def get_redis_client():
    return redis.Redis(host="redis")


def register_defaults():
    # registers student by id
    for s in students:
        r.set(s.get('id'), json.dumps(s))


def get_student(id, redis_client):
    if 'photo' in str(id):
        print('pass')
    else:
        return dict(json.loads(redis_client.get(id)))


def get_all():
    keys = r.keys('*')
    out = [get_student(k, r) for k in keys]
    return out

# =============================== REST API FUNCTIONS ================================


@app.get("/")
def read_root():
    return "This is a dummy student registry for admins to manipulate student account details"


@app.put("/login")
def admin_login(id: str, pwd: str):
    global login

    if login:
        return f"Already logged in as {login_id}"

    if (id == login_id) and (pwd == login_pass):
        login = True
        return f"Logged in successfully as {id}"
    else:
        return "Login failed."


@app.put("/logout")
def admin_logout():
    global login
    login = False
    return "Succesfully logged out"


@app.get("/students/{student_id}")
def find_student(student_id: str, response: Response, request: Request):
    if login:

        try:
            out = get_student(student_id, r)
            if out:
                return out
        except:
            response.status_code = 404
            return None
    else:
        return "Please login to access this function"


@app.get('/students')
def get_students(sortBy: Optional[str] = None, count: Optional[int] = None, offset: Optional[int] = None):
    if login:
        out = get_all()
        if sortBy:
            out = sorted(out, key=itemgetter(sortBy))
        if offset:
            out = out[offset:]
        if count:
            out = out[:count]

        return out
    else:
        return "Please login to access this function"


@app.post("/newstudent")
def create_student(student: Student, response: Response, redis_client: redis.Redis = Depends(get_redis_client)):
    if login:
        stud = student.dict()
        if (len(stud.get('id')) != 7) or (stud.get('id')[:3] != '100'):
            return 'Invalid id format. Ensure id is 7 digits in the format 100xxxx.'

        redis_client.set(student.dict().get(
            'id'), json.dumps(student.dict()))
        return "Student created"

    else:
        return "Please login to access this function"


@app.put("/assignnew")
def assign_new(id: str, hw: str, redis_client: redis.Redis = Depends(get_redis_client)):
    if login:
        stu = get_student(id, redis_client)
        stu['assignment'] = stu['assignment'] + ',' + hw
        redis_client.set(id, json.dumps(stu))

        return f"Successfully assigned new homework to {stu.get('name')}. Assignments are now {stu.get('assignment')}"

    else:
        return "Please login to access this function"


@app.delete("/delstudent")
def delete_student(id: str, response: Response, redis_client: redis.Redis = Depends(get_redis_client)):
    if login:
        try:
            name = dict(json.loads(redis_client.get(id))).get('name')
            redis_client.delete(id)
            return f"Successfully deleted student {id}, {name}"
        except:
            response.status_code = 404
            return None
    else:
        return "Please login to access this function"


@app.put("/updatepassword")
def update_password(id: str, npass: str, redis_client: redis.Redis = Depends(get_redis_client)):
    if login:
        student = get_student(id, redis_client)
        old = student.get('password')
        student['password'] = npass
        redis_client.set(id, json.dumps(student))
        return f"{student.get('name')}'s Password updated from {old} to {student.get('password')}"
    else:
        return "Please login to access this function"


@app.put("/setphoto")
def set_photo(request: Request, id: str, photo: str = "/app/sample.jpg", redis_client: redis.Redis = Depends(get_redis_client)):
    if login:
        if request.headers['Accept'] == 'image/jpeg':
            key = id + 'photo'
            output = BytesIO()
            im = Image.open(photo)
            im.save(output, format=im.format)
            redis_client.set(key, output.getvalue())
            output.close()
            return 'File saved as bytestring'
    else:
        return "Please login to access this function"


@app.get("/getphoto")
def get_photo(request: Request, id: str, redis_client: redis.Redis = Depends(get_redis_client)):
    if login:
        if request.headers['Accept'] == 'image/jpeg':
            key = id + 'photo'
            bytes = redis_client.get(key)
            image = Image.open(BytesIO(bytes))
            image.save(f'/app/{key}.jpg')
            return 'Photo downloaded'


@app.delete("/reset")
def reset(key: str, redis_client: redis.Redis = Depends(get_redis_client)):
    if login:
        if key == wipe_key:
            redis_client.flushdb()
            register_defaults()
            return "Database reset to default state."
    else:
        return "Please login to access this function"


if __name__ == '__main__':
    register_defaults()
