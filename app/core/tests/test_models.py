"""
Test for models
"""
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from core import models

def create_user(email='user@example.com', password='testpass123'):
    """Helper function to create a user"""
    return get_user_model().objects.create_user(email, password)

class ModelTests(TestCase):
    """Test for models"""

    def test_create_user_with_email_successful(self):
        """Test creating a new user with an email is successful"""
        email = 'test@example.com'
        password = 'testpass123'
        user = get_user_model().objects.create_user(
            email=email,
            password=password
        )

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalized(self):
        """Test  the email for a new user is normalized"""
        sample_email = [
            ['test1@example.com', 'test1@example.com'],
            ['test2@EXAMPLE.com', 'test2@example.com'],
            ['Test3@Example.com', 'Test3@example.com'],
            ['TEST4@EXAMPLE.com', 'TEST4@example.com'],
            ['test5@example.COM', 'test5@example.com'],
        ]

        for email, expected in sample_email:
            user = get_user_model().objects.create_user(email, 'test123')
            self.assertEqual(user.email, expected)

    def test_new_user_without_email_raises_error(self):
        """Test that creating user without email raises error"""
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user('', 'test123')

    def test_create_superuser(self):
        """Test creating a new superuser"""
        user = get_user_model().objects.create_superuser(
            'test@example.com',
            'test123',
        )

        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_create_recipe(self):
        """Test creating a new recipe is successful"""
        user = get_user_model().objects.create_user(
            'test@example.com',
            'test123',
        )
        recipe = models.Recipe.objects.create(
            user=user,
            title='Test recipe',
            time_minutes=5,
            price=Decimal('5.50'),
            description='Test description',
        )

        self.assertEqual(str(recipe), recipe.title)

    def test_create_tag(self):
        """Test creating a new tag is successful"""
        user = create_user()
        tag = models.Tag.objects.create(
            user=user,
            name='Test tag1',
        )

        self.assertEqual(str(tag), tag.name)
