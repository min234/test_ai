
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_add(client):
    """Test the add route."""
    response = client.get('/add/2/3')
    json_data = response.get_json()
    assert response.status_code == 200
    assert json_data['result'] == 5

def test_add_negative(client):
    """Test the add route with negative numbers."""
    response = client.get('/add/-2/-3')
    json_data = response.get_json()
    assert response.status_code == 200
    assert json_data['result'] == -5
