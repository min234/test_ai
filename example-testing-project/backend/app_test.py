import pytest
from app import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_add(client):
    response = client.get('/add/2/3')
    json_data = response.get_json()
    assert response.status_code == 200
    assert json_data['result'] == 5

def test_add_negative(client):
    response = client.get('/add/-1/-1')
    json_data = response.get_json()
    assert response.status_code == 200
    assert json_data['result'] == -2

def test_add_zero(client):
    response = client.get('/add/0/0')
    json_data = response.get_json()
    assert response.status_code == 200
    assert json_data['result'] == 0

def test_add_large_numbers(client):
    response = client.get('/add/1000/2000')
    json_data = response.get_json()
    assert response.status_code == 200
    assert json_data['result'] == 3000