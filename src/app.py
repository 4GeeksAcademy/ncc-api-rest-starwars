"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
import os
from flask import Flask, request, jsonify, url_for
from flask_migrate import Migrate
from flask_swagger import swagger
from flask_cors import CORS
from utils import APIException, generate_sitemap
from admin import setup_admin
from models import db, Personaje, Usuario, Planeta, PlanetaFavorito, PersonajeFavorito

app = Flask(__name__)
app.url_map.strict_slashes = False

db_url = os.getenv("DATABASE_URL")
if db_url is not None:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace(
        "postgres://", "postgresql://")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:////tmp/test.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

MIGRATE = Migrate(app, db)
db.init_app(app)
CORS(app)
setup_admin(app)

# Handle/serialize errors like a JSON object


@app.errorhandler(APIException)
def handle_invalid_usage(error):
    return jsonify(error.to_dict()), error.status_code

# generate sitemap with all your endpoints


@app.route('/')
def sitemap():
    return generate_sitemap(app)


@app.route('/user', methods=['GET'])
def handle_hello():

    response_body = {
        "msg": "Hello, this is your GET /user response "
    }

    return jsonify(response_body), 200


@app.route('/people', methods=['GET'])
def list_people():
    """Listar todos los registros de personajes"""
    personajes = Personaje.query.all()
    result = [p.serialize() if hasattr(p, 'serialize') else {
        "id": p.id, "nombre": getattr(p, 'nombre', None)} for p in personajes]
    return jsonify(result), 200


@app.route('/people/<int:people_id>', methods=['GET'])
def get_person(people_id):
    """Mostrar la información de un solo personaje por id"""
    personaje = Personaje.query.get(people_id)
    if personaje is None:
        return jsonify({"message": "Personaje no encontrado"}), 404
    return jsonify(personaje.serialize() if hasattr(personaje, 'serialize') else {"id": personaje.id, "nombre": getattr(personaje, 'nombre', None)}), 200


@app.route('/planets', methods=['GET'])
def list_planets():
    """Listar todos los planetas"""
    planetas = Planeta.query.all()
    result = [p.serialize() if hasattr(p, 'serialize') else {
        "id": p.id, "nombre": getattr(p, 'nombre', None)} for p in planetas]
    return jsonify(result), 200


@app.route('/planets/<int:planet_id>', methods=['GET'])
def get_planet(planet_id):
    """Mostrar la información de un solo planeta por id"""
    planeta = Planeta.query.get(planet_id)
    if planeta is None:
        return jsonify({"message": "Planeta no encontrado"}), 404
    return jsonify(planeta.serialize() if hasattr(planeta, 'serialize') else {"id": planeta.id, "nombre": getattr(planeta, 'nombre', None)}), 200


@app.route('/users', methods=['GET'])
def list_users():
    """Listar todos los registros de usuarios"""
    usuarios = Usuario.query.all()
    result = [u.serialize() if hasattr(u, 'serialize') else {
        "id": u.id, "email": getattr(u, 'email', None)} for u in usuarios]
    return jsonify(result), 200


@app.route('/users/favorites', methods=['GET'])
def list_user_favorites():
    """Listar favoritos del usuario actual.

    Se acepta el id de usuario vía query param `user_id` o cabecera `X-User-Id`.
    Si no se provee, por conveniencia se usa `1`.
    """

    user_id = request.args.get('user_id', type=int)
    if not user_id:
        header_id = request.headers.get('X-User-Id')
        try:
            user_id = int(header_id) if header_id is not None else None
        except Exception:
            user_id = None
    if not user_id:
        user_id = 1

    usuario = Usuario.query.get(user_id)
    if usuario is None:
        return jsonify({"message": "Usuario no encontrado"}), 404

    planetas = []
    for fav in getattr(usuario, 'planetas_favoritos', []):
        planeta = getattr(fav, 'planeta', None)
        planetas.append({
            "id": fav.id,
            "planeta": planeta.serialize() if planeta and hasattr(planeta, 'serialize') else {"id": getattr(planeta, 'id', None), "nombre": getattr(planeta, 'nombre', None)},
            "fecha_agregado": getattr(fav, 'fecha_agregado', None).isoformat() if getattr(fav, 'fecha_agregado', None) is not None else None
        })

    personajes = []
    for fav in getattr(usuario, 'personajes_favoritos', []):
        personaje = getattr(fav, 'personaje', None)
        personajes.append({
            "id": fav.id,
            "personaje": personaje.serialize() if personaje and hasattr(personaje, 'serialize') else {"id": getattr(personaje, 'id', None), "nombre": getattr(personaje, 'nombre', None)},
            "fecha_agregado": getattr(fav, 'fecha_agregado', None).isoformat() if getattr(fav, 'fecha_agregado', None) is not None else None
        })

    return jsonify({"usuario_id": usuario.id, "planetas": planetas, "personajes": personajes}), 200


@app.route('/favorite/planet/<int:planet_id>', methods=['POST'])
def add_favorite_planet(planet_id):
    """Añadir un planeta favorito al usuario actual"""
    # identificar usuario (query param -> header -> default 1)
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        header_id = request.headers.get(
            'X-User-Id') or request.headers.get('X-USER-ID')
        try:
            user_id = int(header_id) if header_id is not None else None
        except Exception:
            user_id = None
    if not user_id:
        user_id = 1

    usuario = Usuario.query.get(user_id)
    if usuario is None:
        return jsonify({"message": "Usuario no encontrado"}), 404

    planeta = Planeta.query.get(planet_id)
    if planeta is None:
        return jsonify({"message": "Planeta no encontrado"}), 404

    existing = PlanetaFavorito.query.filter_by(
        usuario_id=usuario.id, planeta_id=planet_id).first()
    if existing:
        return jsonify({"message": "Planeta ya es favorito"}), 400

    fav = PlanetaFavorito(usuario_id=usuario.id, planeta_id=planet_id)
    db.session.add(fav)
    db.session.commit()

    return jsonify(fav.serialize() if hasattr(fav, 'serialize') else {"id": fav.id, "usuario_id": fav.usuario_id, "planeta_id": fav.planeta_id}), 201


@app.route('/favorite/people/<int:people_id>', methods=['POST'])
def add_favorite_people(people_id):
    """Añadir un personaje favorito al usuario actual"""
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        header_id = request.headers.get(
            'X-User-Id') or request.headers.get('X-USER-ID')
        try:
            user_id = int(header_id) if header_id is not None else None
        except Exception:
            user_id = None
    if not user_id:
        user_id = 1

    usuario = Usuario.query.get(user_id)
    if usuario is None:
        return jsonify({"message": "Usuario no encontrado"}), 404

    personaje = Personaje.query.get(people_id)
    if personaje is None:
        return jsonify({"message": "Personaje no encontrado"}), 404

    existing = PersonajeFavorito.query.filter_by(
        usuario_id=usuario.id, personaje_id=people_id).first()
    if existing:
        return jsonify({"message": "Personaje ya es favorito"}), 400

    fav = PersonajeFavorito(usuario_id=usuario.id, personaje_id=people_id)
    db.session.add(fav)
    db.session.commit()

    return jsonify(fav.serialize() if hasattr(fav, 'serialize') else {"id": fav.id, "usuario_id": fav.usuario_id, "personaje_id": fav.personaje_id}), 201


@app.route('/favorite/planet/<int:planet_id>', methods=['DELETE'])
def delete_favorite_planet(planet_id):
    """Eliminar un planeta favorito del usuario actual"""
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        header_id = request.headers.get(
            'X-User-Id') or request.headers.get('X-USER-ID')
        try:
            user_id = int(header_id) if header_id is not None else None
        except Exception:
            user_id = None
    if not user_id:
        user_id = 1

    fav = PlanetaFavorito.query.filter_by(
        usuario_id=user_id, planeta_id=planet_id).first()
    if not fav:
        return jsonify({"message": "Favorito no encontrado"}), 404

    db.session.delete(fav)
    db.session.commit()
    return ('', 204)


@app.route('/favorite/people/<int:people_id>', methods=['DELETE'])
def delete_favorite_people(people_id):
    """Eliminar un personaje favorito del usuario actual"""
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        header_id = request.headers.get(
            'X-User-Id') or request.headers.get('X-USER-ID')
        try:
            user_id = int(header_id) if header_id is not None else None
        except Exception:
            user_id = None
    if not user_id:
        user_id = 1

    fav = PersonajeFavorito.query.filter_by(
        usuario_id=user_id, personaje_id=people_id).first()
    if not fav:
        return jsonify({"message": "Favorito no encontrado"}), 404

    db.session.delete(fav)
    db.session.commit()
    return ('', 204)


# this only runs if `$ python src/app.py` is executed
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=PORT, debug=False)
