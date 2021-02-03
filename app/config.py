CSRF_ENABLED = True
# TODO: what is SECRET_KEY?
SECRET_KEY = 'you-will-never-guess'
UPLOAD_FOLDER = './static/worker-pdf'
REDIS_URL = 'redis://redis:6379/0'
BROKER_USERNAME = 'admin'
BROKER_PASSWORD = 'mypass'
BROKER_SERVER = 'rabbit'
BROKER_PORT = 5672
BROKER_URL = 'amqp://{}:{}@{}://'.format(BROKER_USERNAME, BROKER_PASSWORD, BROKER_SERVER, BROKER_PORT)