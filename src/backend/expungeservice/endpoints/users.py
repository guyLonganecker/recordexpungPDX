from flask.views import MethodView
from flask import request, abort, jsonify
from werkzeug.security import generate_password_hash

from flask import g
from expungeservice.database import user
from expungeservice.endpoints.auth import admin_auth_required
from expungeservice.request import check_data_fields
from psycopg2.errors import UniqueViolation
from expungeservice.request.error import error


class Users(MethodView):
    @admin_auth_required
    def post(self):
        """
        Create a new user with provided email, password, and admin flag.
        - If required fields are missing in the request, return 400
        - Password must be 8 or more characters long. Otherwise return 422
        - Email must not already be in use by an existing user.
          Otherwise return 422
        - If success, return 201 with the new user's email, admin flag,
          and creation timestamp.
        """

        data = request.get_json()

        if data is None:
            error(400, "No json data in request body")

        # print("data received by Users.post():", data)
        check_data_fields(data, ['email', 'name', 'group_name',
                                 'password', 'admin'])

        if len(data['password']) < 8:
            error(422, 'New password is less than 8 characters long!')

        password_hash = generate_password_hash(data['password'])

        try:
            create_user_result = user.create(
                g.database,
                email=data['email'],
                name=data['name'],
                group_name=data['group_name'],
                password_hash=password_hash,
                admin=data['admin'])

        except UniqueViolation:
            error(422, 'User with that email address already exists')

        response_data = {
            'email': create_user_result['email'],
            'admin': create_user_result['admin'],
            'timestamp': create_user_result['date_created'],
        }
        # user_id is not required by the frontend here so it is not included.
        # other endpoints may expose the user_id e.g. for other admin
        # user-management operations.

        return jsonify(response_data), 201

    @admin_auth_required
    def get(self):
        """
        Fetch the list of users, including their email, admin clear
        """

        user_db_data = user.fetchall(g.database)

        response_data = {'users': []}
        for user_entry in user_db_data:
            response_data['users'].append({
                'user_id': user_entry['user_id'],
                'email': user_entry['email'],
                'name': user_entry['name'],
                'group_name': user_entry['group_name'],
                'admin': user_entry['admin'],
                'timestamp': user_entry['date_created']
                })

        return jsonify(response_data), 201


def register(app):
    app.add_url_rule('/api/users', view_func=Users.as_view('users'))