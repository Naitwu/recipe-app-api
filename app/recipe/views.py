"""
Views for recipe app
"""
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
)

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets, mixins, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from django.conf import settings

from core.models import Recipe, Tag
from recipe import serializers

import boto3
from botocore.exceptions import NoCredentialsError

ACCESS_KEY_ID='AKIAWXZHTXAE2IP4B2RX'
SECRET_ACCESS_KEY='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'

def s3_image_rekognition(user_email, filename, image, recipe_id):
    s3_client = boto3.client('s3',aws_access_key_id=ACCESS_KEY_ID, aws_secret_access_key=SECRET_ACCESS_KEY, region_name='us-east-1')
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    s3_file_key = f"{user_email.split('@')[0]}/{filename}"

    try:
        s3_client.upload_fileobj(image, bucket_name, s3_file_key)
    except NoCredentialsError:
        return {"error": "Credentials not available"}

    presigned_url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': s3_file_key},
        ExpiresIn=604800
    )

    rekognition_client = boto3.client('rekognition', aws_access_key_id=ACCESS_KEY_ID, aws_secret_access_key=SECRET_ACCESS_KEY, region_name='us-east-1')

    try:
        response = rekognition_client.detect_labels(
            Image={'S3Object': {'Bucket': bucket_name, 'Name': s3_file_key}},
            MaxLabels=10
        )
    except NoCredentialsError:
        return {"error": "Credentials not available for Rekognition"}

    simplified_labels = [{"Name": label["Name"], "Confidence": label["Confidence"]} for label in response['Labels']]

    return {
        "presigned_url": presigned_url,
        "labels": simplified_labels
    }


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                'tags',
                OpenApiTypes.STR,
                description='Comma separated list of tagsIDs to filter recipes by tags  e.g. 2,3',
            )
        ]
    )
)
class RecipeViewSet(viewsets.ModelViewSet):
    """View for manage recipe api"""
    serializer_class = serializers.RecipeDetailSerializer
    queryset = Recipe.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _params_to_ints(self, qs):
        """Convert a list of string IDs to a list of integers"""
        return [int(str_id) for str_id in qs.split(',')]

    def get_queryset(self):
        """Return objects for the current authenticated user only"""
        tags =  self.request.query_params.get('tags')
        queryset = self.queryset
        if tags:
            tag_ids = self._params_to_ints(tags)
            queryset = queryset.filter(tags__id__in=tag_ids)

        return queryset.filter(user=self.request.user).order_by('-id').distinct()

    def get_serializer_class(self):
        """Return the serializer class for request"""
        if self.action == 'list':
            return serializers.RecipeSerializer
        elif self.action == 'upload_image':
            return serializers.RecipeImageSerializer

        return self.serializer_class

    def perform_create(self, serializer):
        """Create a new recipe"""
        serializer.save(user=self.request.user)

    @action(methods=['POST'], detail=True, url_path='upload-image')
    def upload_image(self, request, pk=None):
        """Upload an image to a recipe"""
        recipe = self.get_object()
        serializer = self.get_serializer(recipe, data=request.data)

        if serializer.is_valid():
            serializer.save()

            image_file = request.FILES.get('image')
            if image_file:
                user_email = request.user.email
                filename = image_file.name
                result = s3_image_rekognition(user_email, filename, image_file, pk)

            if 'error' in result:
                return Response({"error": result["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response(result, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                'assigned_only',
                OpenApiTypes.INT,enum=[0, 1, 2],
                description='Filter by items that are assigned or not assigned  to recipes \
                             0=All, 1=Assigned only, 2=Not assigned only',
            )
        ]
    )
)
class TagViewSet(mixins.DestroyModelMixin,
                 mixins.UpdateModelMixin,
                 mixins.ListModelMixin,
                 viewsets.GenericViewSet):
    serializer_class = serializers.TagSerializer
    queryset = Tag.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return objects for the current authenticated user only"""
        assigned_only = int(self.request.query_params.get('assigned_only', 0))
        queryset = self.queryset
        if assigned_only == 1:
            queryset = queryset.filter(recipe__isnull=False)
        elif assigned_only == 2:
            queryset = queryset.filter(recipe__isnull=True)
        return queryset.filter(user=self.request.user).order_by('-name').distinct()
