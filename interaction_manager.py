import base64
import datetime
import io
import json
from typing import Optional

import flask
import sqlalchemy.orm
from flask import Response
from reportlab.lib.colors import black
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from feria import User, engine, UserSession, Feria, UserType, Stand


def serialize_feria(feria):
    return {'name': feria.name, 'date': feria.date.strftime("%Y-%m-%d"), 'count': feria.stand_count,
            'owner': feria.owner,
            'stands': [((s.nombre + " - ") if s.nombre else '') + s.responsable_nombre for s in feria.stands],
            'amigo': feria.amigo_invisible}


class FeriaInteraction:
    def __init__(self, request):
        self.request: flask.Request = request
        self.user: Optional[User] = None

    def __enter__(self):
        self.session = sqlalchemy.orm.Session(engine)
        print(self.request.cookies)
        if 'session_id' in self.request.cookies:
            try:
                user_session, = self.session.execute(sqlalchemy.select(UserSession).where(
                    UserSession.session_id == self.request.cookies.get('session_id'))).first()
                self.user, = self.session.execute(
                    sqlalchemy.select(User).where(User.username == user_session.username)).first()
            except:
                pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.commit()
        self.session.close()

    def detalle_feria(self, nombre):
        feria, = self.session.execute(sqlalchemy.select(Feria).where(Feria.name == nombre)).first()
        feria.date: datetime.datetime
        feria_details = serialize_feria(feria)
        return Response(json.dumps(feria_details))

    def user_info(self):
        if self.user is not None:
            user_info = {'logged_in': True, 'name': self.user.username, 'type': str(self.user.user_type)}
        else:
            user_info = {'logged_in': False}
        return Response(json.dumps(user_info))

    def login(self):
        auth = self.request.headers.get('Authorization').split()[-1]
        username, password = base64.b64decode(auth).decode().split(":")
        user, = self.session.execute(sqlalchemy.select(User).where(User.username == username)).first()
        if user.check_password(password):
            r = Response(json.dumps({'success': True}), status=200)
            session = UserSession(user)
            self.session.add(session)
            r.set_cookie('session_id', session.session_id)
            return r
        else:
            return Response(json.dumps({'success': False}), status=401)

    def create_user(self, username, password, user_type):
        if self.user is None:
            return Response(json.dumps({'error': 'Not authorized!', 'success': False}), status=401)
        if (user_type in [UserType.ADMIN, UserType.MOD] and
                self.user.user_type not in [UserType.ADMIN]):
            return Response(json.dumps({'error': f'{self.user.user_type} ∉ {UserType.ADMIN}', 'success': False}),
                            status=401)
        user = User(username, password, user_type)
        self.session.add(user)
        return Response(json.dumps({'success': True}))

    def create_feria(self, feria_name, stand_count, date):
        if self.user is None:
            return Response(json.dumps({'error': 'Not authorized!', 'success': False}), status=401)
        if (self.user.user_type not in [UserType.ADMIN, UserType.MOD]):
            return Response(
                json.dumps({'error': f'{self.user.user_type} ∉ {UserType.ADMIN, UserType.MOD}', 'success': False}),
                status=401)
        feria = Feria(self.user, feria_name, date, stand_count)
        self.session.add(feria)
        return Response(json.dumps({'success': True}))

    def registrar_feria(self, feria: Feria, nombre, responsable_dni, responsable_nombre):
        if len(feria.stands) >= feria.stand_count:
            return Response(json.dumps({'success': False, 'error': 'La feria ya llegó a su límite de stands!'}))
        if self.user is None or (self.user.user_type != UserType.ADMIN and self.user.username != feria.owner):
            return Response(
                json.dumps({'success': False, 'error': 'No estás autorizado a registrar gente en esta feria!'}))
        stand = Stand(feria, nombre, responsable_dni, responsable_nombre, None)
        self.session.add(stand)
        self.session.commit()
        return Response(json.dumps(
            {'success': True, 'id': sorted(feria.stands, key=lambda x: x.fecha_inscripcion).index(stand) + 1}))

    def find_feria(self, name) -> Feria:
        feria, = self.session.execute(sqlalchemy.select(Feria).where(Feria.name == name)).first()
        return feria

    def list_feria(self):
        feria = self.session.execute(sqlalchemy.select(Feria)).all()
        return Response(json.dumps(
            [serialize_feria(feria) for (feria,) in
             feria]))

    def generate_amigo(self, nombre):
        feria = self.find_feria(nombre)
        if self.user is None or (self.user.user_type != UserType.ADMIN and self.user.username != feria.owner):
            return Response(json.dumps({'success': False}), status=401)
        feria.calculate_amigo_invisible()
        self.session.commit()
        return Response(json.dumps({'success': True}), status=200)

    def reporte_feria(self, nombre):
        feria, = self.session.execute(sqlalchemy.select(Feria).where(Feria.name == nombre)).first()
        output = io.BytesIO()
        c = canvas.Canvas(output, pagesize=A4)
        c.translate(0, A4[1])
        c.drawCentredString(A4[0] / 2, -15, feria.name)
        c.drawCentredString(A4[0] / 2, -30, str(feria.date.date()))
        for idx, stand in enumerate(sorted(feria.stands, key=lambda x: x.fecha_inscripcion)):
            c.drawString(0, -60 - (60 * idx), "Stand Numero " + str(idx))
            if stand.nombre is not None:
                c.drawString(0, -60 - (60 * idx) - 15, "Nombre del Stand: " + stand.nombre)
            c.drawString(0, -60 - (60 * idx) - 30,
                         "Responsable: " + stand.responsable_nombre + " DNI " + stand.responsable_dni)
            c.drawString(0, -60 - (60 * idx) - 45, str(stand.fecha_inscripcion))
            c.setStrokeColor(black)
            c.line(0, -60 - (60 * (idx)) - 50, A4[0], -60 - (60 * (idx)) - 50)
        if feria.amigo_invisible:
            start_y = -60 - (60 * len(feria.stands)) - 50
            c.drawCentredString(A4[0] / 2, start_y, "¡Amigo invisible!")
            for idx, (k, v) in enumerate(feria.amigo_invisible.items()):
                c.drawString(0, start_y - 15 * (idx + 1), k)
                c.drawRightString(A4[0], start_y - 15 * (idx + 1), v)
                c.line(0, start_y - 15 * (idx + 1) - 3, A4[0], start_y - 15 * (idx + 1) - 3)
        c.showPage()
        c.save()
        output = output.getvalue()
        print(len(output))
        return Response(output, content_type='application/pdf')
