import base64
import datetime
import enum
import random
import uuid

import bcrypt
import sqlalchemy.orm
import tzlocal

engine = sqlalchemy.create_engine("sqlite+pysqlite:///ferias.db")

mapper = sqlalchemy.orm.registry()

UserType = enum.Enum('UserType', 'ADMIN MOD USER')


@mapper.mapped
class UserSession:
    __tablename__ = "user_sessions"

    def __init__(self, user):
        self.username = user.username
        self.session_id = str(uuid.uuid1())
        self.session_start = datetime.datetime.now(tzlocal.get_localzone())

    username = sqlalchemy.Column(sqlalchemy.Text, sqlalchemy.ForeignKey('users.username'), nullable=False)
    session_id = sqlalchemy.Column(sqlalchemy.Text, primary_key=True)
    session_start = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)


@mapper.mapped
class User:
    __tablename__ = "users"

    username = sqlalchemy.Column(sqlalchemy.Text, primary_key=True)
    password = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    user_type = sqlalchemy.Column(sqlalchemy.Enum(UserType), nullable=False)
    ferias = sqlalchemy.orm.relationship("Feria")
    stands = sqlalchemy.orm.relationship('Stand')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode(), base64.b64decode(self.password))

    def __init__(self, username, password, user_type):
        self.username = username
        self.password = base64.b64encode(bcrypt.hashpw(password.encode(), bcrypt.gensalt()))
        self.user_type = user_type


@mapper.mapped
class Feria:
    __tablename__ = "ferias"

    owner = sqlalchemy.Column(sqlalchemy.Text, sqlalchemy.ForeignKey('users.username'), nullable=False)
    stand_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    name = sqlalchemy.Column(sqlalchemy.Text, primary_key=True)
    date = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    amigo_invisible = sqlalchemy.Column(sqlalchemy.JSON, nullable=True)

    stands = sqlalchemy.orm.relationship('Stand')

    def __init__(self, owner, name, date, stand_count):
        self.stand_count = stand_count
        if owner.user_type not in [UserType.ADMIN, UserType.MOD]:
            raise PermissionError((owner.user_type, "∉", [UserType.ADMIN, UserType.MOD]))
        self.owner = owner.username
        self.name = name
        self.date = date

    def calculate_amigo_invisible(self):
        stands = sorted(self.stands, key=lambda x: x.fecha_inscripcion)
        in_stands = set([f'{s.responsable_nombre} @ {stands.index(s)}' for s in stands])
        out_stands = set(in_stands)

        targets = {}

        got_successful = False
        while not got_successful:
            initial_round = True
            while (len(in_stands) > 0) or (len(out_stands) > 0):
                if in_stands == out_stands and not initial_round:
                    break
                initial_round = False
                s1 = random.choice(list(in_stands))
                s2 = random.choice(list(out_stands - {s1}))
                in_stands -= {s1}
                out_stands -= {s2}
                targets[s1] = s2
            got_successful = len(in_stands) == 0 and len(out_stands) == 0
        self.amigo_invisible = targets
        return targets

    def __str__(self):
        return f'{self.name} // {self.date}' + (
            "" if self.owner is None else f"administrado por {self.owner}") + f" // ({len(self.stands)} / {self.stand_count})"


@mapper.mapped
class Stand:
    __tablename__ = "stands"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)

    feria = sqlalchemy.Column(sqlalchemy.Text, sqlalchemy.ForeignKey('ferias.name'), nullable=False)

    nombre = sqlalchemy.Column(sqlalchemy.Text, nullable=True)

    fecha_inscripcion = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)

    responsable_dni = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    responsable_nombre = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    usuario_responsable = sqlalchemy.Column(sqlalchemy.Text, sqlalchemy.ForeignKey('users.username'), nullable=True)

    def __init__(self, feria, nombre, responsable_dni, responsable_nombre, usuario_responsable):
        self.feria = feria.name
        self.nombre = nombre
        self.responsable_dni = responsable_dni
        self.responsable_nombre = responsable_nombre
        self.usuario_responsable = usuario_responsable
        self.fecha_inscripcion = datetime.datetime.now(tzlocal.get_localzone())


mapper.metadata.bind = engine
mapper.metadata.create_all()
