from django.http import JsonResponse

class ApiErrorResponse(JsonResponse):
    def __init__(self, status_code, message, details=None):
        response_body = {
            'error': {
                'code': status_code,
                'message': message,
                'details': details
            }
        }
        super().__init__(response_body)
        self.status_code = status_code
