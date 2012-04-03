from nose.tools import eq_, ok_, raises

from flask import Flask

from flask.ext import wtf

from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.adminex import Admin
from flask.ext.adminex.ext.sqlamodel import ModelView


class CustomModelView(ModelView):
    def __init__(self, model, session,
                 name=None, category=None, endpoint=None, url=None,
                 **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)

        super(CustomModelView, self).__init__(model, session,
                                              name, category,
                                              endpoint, url)


def create_models(db):
    class Model1(db.Model):
        def __init__(self, test1=None, test2=None, test3=None, test4=None):
            self.test1 = test1
            self.test2 = test2
            self.test3 = test3
            self.test4 = test4

        id = db.Column(db.Integer, primary_key=True)
        test1 = db.Column(db.String(20))
        test2 = db.Column(db.Unicode(20))
        test3 = db.Column(db.Text)
        test4 = db.Column(db.UnicodeText)

    class Model2(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        int_field = db.Column(db.Integer)
        bool_field = db.Column(db.Boolean)

    db.create_all()

    return Model1, Model2


def setup():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = '1'
    app.config['CSRF_ENABLED'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'

    db = SQLAlchemy(app)
    admin = Admin(app)

    return app, db, admin


def test_model():
    app, db, admin = setup()
    Model1, Model2 = create_models(db)
    db.create_all()

    view = CustomModelView(Model1, db.session)
    admin.add_view(view)

    eq_(view.model, Model1)
    eq_(view.name, 'Model1')
    eq_(view.endpoint, 'model1view')

    eq_(view._primary_key, 'id')
    eq_(view._sortable_columns, dict(test1='test1',
                                     test2='test2',
                                     test3='test3',
                                     test4='test4'))
    ok_(view._create_form_class is not None)
    ok_(view._edit_form_class is not None)
    eq_(view._search_supported, False)
    eq_(view._filters, None)

    # Verify form
    eq_(view._create_form_class.test1.field_class, wtf.TextField)
    eq_(view._create_form_class.test2.field_class, wtf.TextField)
    eq_(view._create_form_class.test3.field_class, wtf.TextAreaField)
    eq_(view._create_form_class.test4.field_class, wtf.TextAreaField)

    # Make some test clients
    client = app.test_client()

    rv = client.get('/admin/model1view/')
    eq_(rv.status_code, 200)

    rv = client.get('/admin/model1view/new/')
    eq_(rv.status_code, 200)

    rv = client.post('/admin/model1view/new/',
                     data=dict(test1='test1large', test2='test2'))
    eq_(rv.status_code, 302)

    model = db.session.query(Model1).first()
    eq_(model.test1, 'test1large')
    eq_(model.test2, 'test2')
    eq_(model.test3, '')
    eq_(model.test4, '')

    rv = client.get('/admin/model1view/')
    eq_(rv.status_code, 200)
    ok_('test1large' in rv.data)

    url = '/admin/model1view/edit/%d/' % model.id
    rv = client.get(url)
    eq_(rv.status_code, 200)

    rv = client.post(url,
                     data=dict(test1='test1small', test2='test2large'))
    eq_(rv.status_code, 302)

    model = db.session.query(Model1).first()
    eq_(model.test1, 'test1small')
    eq_(model.test2, 'test2large')
    eq_(model.test3, '')
    eq_(model.test4, '')

    url = '/admin/model1view/delete/%d/' % model.id
    rv = client.post(url)
    eq_(rv.status_code, 302)
    eq_(db.session.query(Model1).count(), 0)


@raises(Exception)
def test_no_pk():
    app, db, admin = setup()

    class Model(db.Model):
        test = db.Column(db.Integer)

    view = CustomModelView(Model)
    admin.add_view(view)


def test_list_columns():
    app, db, admin = setup()

    Model1, Model2 = create_models(db)

    view = CustomModelView(Model1, db.session,
                           list_columns=['test1', 'test3'],
                           rename_columns=dict(test1='Column1'))
    admin.add_view(view)

    eq_(len(view._list_columns), 2)
    eq_(view._list_columns, [('test1', 'Column1'), ('test3', 'Test3')])

    client = app.test_client()

    rv = client.get('/admin/model1view/')
    ok_('Column1' in rv.data)
    ok_('Test2' not in rv.data)


def test_exclude_columns():
    app, db, admin = setup()

    Model1, Model2 = create_models(db)

    view = CustomModelView(Model1, db.session,
                           excluded_list_columns=['test2', 'test4'])
    admin.add_view(view)

    eq_(view._list_columns, [('test1', 'Test1'), ('test3', 'Test3')])

    client = app.test_client()

    rv = client.get('/admin/model1view/')
    ok_('Test1' in rv.data)
    ok_('Test2' not in rv.data)


def test_searchable_columns():
    app, db, admin = setup()

    Model1, Model2 = create_models(db)

    view = CustomModelView(Model1, db.session,
                           searchable_columns=['test1', 'test2'])
    admin.add_view(view)

    eq_(view._search_supported, True)
    eq_(len(view._search_fields), 2)
    ok_(isinstance(view._search_fields[0], db.Column))
    ok_(isinstance(view._search_fields[1], db.Column))
    eq_(view._search_fields[0].name, 'test1')
    eq_(view._search_fields[1].name, 'test2')

    db.session.add(Model1('model1'))
    db.session.add(Model1('model2'))
    db.session.commit()

    client = app.test_client()

    rv = client.get('/admin/model1view/?search=model1')
    ok_('model1' in rv.data)
    ok_('model2' not in rv.data)


def test_column_filters():
    app, db, admin = setup()

    Model1, Model2 = create_models(db)

    view = CustomModelView(Model1, db.session,
                           column_filters=['test1'])
    admin.add_view(view)

    eq_(len(view._filters), 4)

    eq_(view._filter_names, ['Test1 equals', 'Test1 not equal',
                             'Test1 like', 'Test1 not like'])

    db.session.add(Model1('model1'))
    db.session.add(Model1('model2'))
    db.session.add(Model1('model3'))
    db.session.add(Model1('model4'))
    db.session.commit()

    client = app.test_client()

    rv = client.get('/admin/model1view/?flt0=0&flt0v=model1')
    eq_(rv.status_code, 200)
    ok_('model1' in rv.data)
    ok_('model2' not in rv.data)

    rv = client.get('/admin/model1view/?flt0=5')
    eq_(rv.status_code, 200)
    ok_('model1' in rv.data)
    ok_('model2' in rv.data)

    # Test different filter types
    view = CustomModelView(Model2, db.session,
                           column_filters=['int_field'])
    admin.add_view(view)

    eq_(view._filter_names, ['Int Field equals',
                             'Int Field not equal',
                             'Int Field greater than',
                             'Int Field smaller than'])


def test_url_args():
    app, db, admin = setup()

    Model1, Model2 = create_models(db)


def test_form():
    # TODO: form_columns
    # TODO: excluded_form_columns
    # TODO: form_args
    pass
