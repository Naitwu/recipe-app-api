"""
Test the recipe API
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe, Tag

from recipe.serializers import RecipeSerializer, RecipeDetailSerializer


RECIPES_URL = reverse('recipe:recipe-list')


def detail_url(recipe_id):
    """Create and Return recipe detail URL"""
    return reverse('recipe:recipe-detail', args=[recipe_id])


def create_recipe(user, **params):
    """Helper function to create a recipe"""
    defaults = {
        'title': 'Sample recipe title',
        'description': 'Sample description',
        'time_minutes': 66,
        'price': Decimal('5.25'),
        'link': 'https://example.com/recipe.pdf',
    }
    tags = params.pop('tags', [])
    defaults.update(params)
    recipe = Recipe.objects.create(user=user, **defaults)

    for tag in tags:
        recipe.tags.add(tag)

    return recipe


def create_user(**params):
    """Helper function to create a user"""
    return get_user_model().objects.create_user(**params)


class PublicRecipeApiTests(TestCase):
    """Test unauthenticated recipe API access"""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test that authentication is required"""
        res = self.client.get(RECIPES_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeApiTests(TestCase):
    """Test authenticated recipe API access"""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email='user@example.com', password='testpass123')
        self.client.force_authenticate(self.user)

    def test_retrieve_recipes(self):
        """Test retrieving a list of recipes"""
        create_recipe(user=self.user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)

        recipes = Recipe.objects.all().order_by('-id')
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_recipes_list_limited_to_user(self):
        """Test list of recipes returned is for authenticated user"""
        other_user = create_user(email='other@example.com', password='testpass123')
        create_recipe(user=other_user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_get_recipe_detail(self):
        """Test get recipe detail"""
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(res.data, serializer.data)

    def test_create_recipe(self):
        """Test create recipe"""
        payload = {
            'title': 'Chocolate cheesecake',
            'description': 'Chocolate cheesecake description',
            'time_minutes': 30,
            'price': Decimal('5.99'),
        }
        res = self.client.post(RECIPES_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=res.data['id'])
        for k, v in payload.items():
            self.assertEqual(v, getattr(recipe, k))
        self.assertEqual(recipe.user, self.user)

    def test_partial_update(self):
        """Test partial update recipe"""
        original_link = 'https://example.com/recipe.pdf'
        recipe = create_recipe(user=self.user, title='Sample recipe title', link=original_link)

        payload = {'title': 'New title'}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(recipe.link, original_link)
        self.assertEqual(self.user, recipe.user)

    def test_full_update(self):
        """Test full update recipe"""
        recipe = create_recipe(
            user=self.user,
            title='Sample recipe title',
            link='https://example.com/recipe.pdf',
            description='Sample description',
            time_minutes=66,
            price=Decimal('6.66')
            )

        payload = {
            'title': 'New title',
            'link': 'https://example.com/new_recipe.pdf',
            'description': 'New description',
            'time_minutes': 77,
            'price': Decimal('7.77')
        }
        url = detail_url(recipe.id)
        res = self.client.put(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        for k,v in payload.items():
            self.assertEqual(v, getattr(recipe, k))
        self.assertEqual(self.user, recipe.user)

    def test_update_user_return_error(self):
        """Test update recipe for other user return error"""
        other_user = create_user(email='other@example.com',password='testpass123')
        recipe = create_recipe(user=self.user)

        payload = {'user': other_user.id}
        url = detail_url(recipe.id)
        self.client.patch(url, payload)

        recipe.refresh_from_db()
        self.assertEqual(recipe.user, self.user)

    def test_delete_recipe(self):
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())

    def test_delete_other_users_recipe_error(self):
        """Test delete other user recipe return error"""
        other_user = create_user(email='other@example.com',password='testpass123')
        recipe = create_recipe(user=other_user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())

    def test_create_recipe_with_new_tags(self):
        """Test create recipe with new tags"""
        payload = {
            'title': 'Chocolate cheesecake',
            'description': 'Chocolate cheesecake description',
            'time_minutes': 30,
            'price': Decimal('5.99'),
            'tags': [{'name': 'Vegan'}, {'name': 'Dessert'}]
        }
        res = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipe.count(), 1)
        recipe = recipe.first()
        self.assertEqual(recipe.tags.count(), 2)
        for tag in payload['tags']:
            exitis = recipe.tags.filter(name=tag['name']).exists()
            self.assertTrue(exitis)

    def test_create_recipe_with_existing_tags(self):
        """Test create recipe with existing tags"""
        tag1 = Tag.objects.create(user=self.user, name='chockolate')
        payload = {
            'title': 'Chocolate cheesecake',
            'description': 'Chocolate cheesecake description',
            'time_minutes': 30,
            'price': Decimal('5.99'),
            'tags': [{'name': 'Vegan'}, {'name': 'chockolate'}]
        }
        res = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipe.count(), 1)
        recipe = recipe.first()
        self.assertEqual(recipe.tags.count(), 2)
        self.assertIn(tag1, recipe.tags.all())
        for tag in payload['tags']:
            exitis = recipe.tags.filter(name=tag['name']).exists()
            self.assertTrue(exitis)

    def test_create_tag_on_update(self):
        """Test creating tag when updating recipe"""
        recipe = create_recipe(user=self.user)

        payload = {'tags': [{'name': 'New tag'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_tag = Tag.objects.filter(user=self.user, name='New tag')
        recipe.refresh_from_db()
        tag_names = [tag.name for tag in recipe.tags.all()]
        self.assertIn('New tag', tag_names)

    def test_update_recipe_with_existing_tags(self):
        """Test update recipe with existing tags"""
        tag1 = Tag.objects.create(user=self.user, name='chockolate')
        tag2 = Tag.objects.create(user=self.user, name='Vegan')
        recipe = create_recipe(user=self.user, tags=[tag1])

        payload = {'tags': [{'name': 'Vegan'}]  }
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(tag2, recipe.tags.all())
        self.assertNotIn(tag1, recipe.tags.all())

    def test_clear_recipe_tags(self):
        """Test clear recipe tags"""
        tag1 = Tag.objects.create(user=self.user, name='chockolate')
        recipe = create_recipe(user=self.user, tags=[tag1])

        payload = {'tags': []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(), 0)

    def test_filter_by_tags(self):
        """Test filter recipes by tags"""
        recipe1 = create_recipe(user=self.user, title='recipe1')
        recipe2 = create_recipe(user=self.user, title='recipe2')
        recipe3 = create_recipe(user=self.user, title='recipe3')
        tag1 = Tag.objects.create(user=self.user, name='chockolate')
        tag2 = Tag.objects.create(user=self.user, name='Vegan')
        recipe1.tags.add(tag1)
        recipe2.tags.add(tag2)

        res = self.client.get(RECIPES_URL, {'tags': f'{tag1.id},{tag2.id}'})

        s1 = RecipeSerializer(recipe1)
        s2 = RecipeSerializer(recipe2)
        s3 = RecipeSerializer(recipe3)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(s1.data, res.data)
        self.assertIn(s2.data, res.data)
        self.assertNotIn(s3.data, res.data)

