from flask import Blueprint

hello = Blueprint('hello', __name__,
                  url_prefix='/v1/hello')

# Route just to ping


@hello.route("/")
async def sayHello():
    return "Hello World!"
