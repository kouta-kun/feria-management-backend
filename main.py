import urllib.parse

import dateutil.parser
import flask

import feria as f
import interaction_manager

app = flask.Flask(__name__)

blueprint = flask.Blueprint(__name__, url_prefix='/api', import_name=__name__)


@blueprint.route('/auth/login', methods=['POST'])
def login():
    with interaction_manager.FeriaInteraction(flask.request) as feria:
        return feria.login()


@blueprint.route('/auth/create', methods=['POST'])
def create_user():
    with interaction_manager.FeriaInteraction(flask.request) as feria:
        feria: interaction_manager.FeriaInteraction
        request_json = flask.request.get_json()
        return feria.create_user(request_json['username'], request_json['password'],
                                 f.UserType[request_json['user_type']])


@blueprint.route('/auth/info', methods=['POST'])
def auth_info():
    with interaction_manager.FeriaInteraction(flask.request) as feria:
        return feria.user_info()


@blueprint.route('/feria/', methods=['GET'])
def list_feria():
    with interaction_manager.FeriaInteraction(flask.request) as feria:
        return feria.list_feria()


@blueprint.route('/feria/create', methods=['POST'])
def create_feria():
    with interaction_manager.FeriaInteraction(flask.request) as feria:
        request_json = flask.request.get_json()
        return feria.create_feria(request_json['nombre'], request_json['count'],
                                  dateutil.parser.isoparse(request_json['date']))


@blueprint.route('/feria/reporte/<nombre>', methods=['GET'])
def reporte_feria(nombre):
    with interaction_manager.FeriaInteraction(flask.request) as feria:
        print(nombre)
        return feria.reporte_feria(nombre)


@blueprint.route('/feria/<nombre>', methods=['GET'])
def detalle_feria(nombre):
    with interaction_manager.FeriaInteraction(flask.request) as feria:
        return feria.detalle_feria(nombre)


@blueprint.route('/feria/register', methods=['POST'])
def register_feria():
    with interaction_manager.FeriaInteraction(flask.request) as feria:
        feria: interaction_manager.FeriaInteraction
        request_json = flask.request.get_json()
        feria_obj = feria.find_feria(urllib.parse.unquote(request_json['feria']))
        return feria.registrar_feria(feria_obj, request_json['nombre'], request_json['dni'],
                                     request_json['responsable'])


@blueprint.route('/feria/amigo/<nombre>', methods=['POST'])
def generar_amigo(nombre):
    with interaction_manager.FeriaInteraction(flask.request) as feria:
        return feria.generate_amigo(nombre)


index_file = None


@app.route("/", methods=['GET'], defaults={'path': ''})
@app.route("/<path:path>", methods=['GET'])
def index(path):
    global index_file
    print(path)
    if index_file is None:
        with open('index.html', 'rb') as file:
            index_file = file.read()
    return index_file


@app.after_request
def after_request(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = 'http://localhost:3000'
    header['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
    header['Access-Control-Allow-Credentials'] = 'true'
    return response


app.register_blueprint(blueprint)

app.run(threaded=True)
