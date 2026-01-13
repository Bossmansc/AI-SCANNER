"""
Security vulnerability tests for the application.
Tests for SQL injection, XSS, CSRF, authentication bypass, and other security issues.
"""

import pytest
import json
import re
import html
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from urllib.parse import quote, unquote

from app import create_app
from app.database import db
from app.models import User, Post, Comment, Session, AuditLog
from app.auth import generate_token, verify_token
from app.utils import sanitize_input, validate_email, hash_password


class TestSQLInjection:
    """Test SQL injection vulnerabilities."""
    
    def setup_method(self):
        """Setup test environment."""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Create test user
        self.test_user = User(
            username='testuser',
            email='test@example.com',
            password_hash=hash_password('TestPass123!')
        )
        db.session.add(self.test_user)
        db.session.commit()
        
        # Get auth token
        self.token = generate_token(self.test_user.id)
    
    def teardown_method(self):
        """Cleanup after tests."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_login_sql_injection_username(self):
        """Test SQL injection in username field during login."""
        # Common SQL injection payloads
        injection_payloads = [
            "' OR '1'='1",
            "' OR '1'='1' --",
            "' OR '1'='1' /*",
            "admin'--",
            "admin'#",
            "' UNION SELECT NULL, username, password FROM users--",
            "' UNION SELECT NULL, NULL, NULL FROM users--",
            "'; DROP TABLE users; --",
            "' OR EXISTS(SELECT * FROM users WHERE username='admin') AND '1'='1",
        ]
        
        for payload in injection_payloads:
            response = self.client.post('/api/auth/login', json={
                'username': payload,
                'password': 'anything'
            })
            
            # Should not return successful login for injection attempts
            if response.status_code == 200:
                data = response.get_json()
                # If login "succeeds" with injection, that's a vulnerability
                if data.get('success') and data.get('token'):
                    pytest.fail(f"SQL injection vulnerability detected with payload: {payload}")
            
            # Check for database errors in response (should be sanitized)
            response_text = response.get_data(as_text=True)
            if any(error in response_text.lower() for error in ['sql', 'syntax', 'database', 'mysql', 'postgresql']):
                pytest.fail(f"Database error exposed with payload: {payload}")
    
    def test_login_sql_injection_password(self):
        """Test SQL injection in password field during login."""
        injection_payloads = [
            "' OR '1'='1",
            "anything' OR 'x'='x",
            "password' UNION SELECT username, password FROM users--",
        ]
        
        for payload in injection_payloads:
            response = self.client.post('/api/auth/login', json={
                'username': 'testuser',
                'password': payload
            })
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success') and data.get('token'):
                    pytest.fail(f"SQL injection vulnerability in password field: {payload}")
    
    def test_search_sql_injection(self):
        """Test SQL injection in search functionality."""
        # First create a post to search for
        post = Post(
            title='Test Post',
            content='This is a test post.',
            user_id=self.test_user.id
        )
        db.session.add(post)
        db.session.commit()
        
        headers = {'Authorization': f'Bearer {self.token}'}
        injection_payloads = [
            "test' OR '1'='1",
            "test' UNION SELECT username, password FROM users--",
            "'; SELECT * FROM users; --",
            "%' OR '1'='1",
        ]
        
        for payload in injection_payloads:
            response = self.client.get(f'/api/posts/search?q={quote(payload)}', headers=headers)
            
            # Should return 400 or empty results, not error
            assert response.status_code in [200, 400, 404]
            
            # Check for database errors
            response_text = response.get_data(as_text=True)
            if any(error in response_text.lower() for error in ['sql', 'syntax', 'database']):
                pytest.fail(f"Search SQL injection vulnerability: {payload}")
    
    def test_user_id_injection(self):
        """Test SQL injection through user_id parameter."""
        headers = {'Authorization': f'Bearer {self.token}'}
        
        injection_payloads = [
            "1 OR 1=1",
            "1; DROP TABLE users;",
            "1 UNION SELECT * FROM users",
            "1' OR '1'='1",
        ]
        
        for payload in injection_payloads:
            response = self.client.get(f'/api/users/{payload}', headers=headers)
            
            # Should return 404 for non-existent users, not error
            assert response.status_code in [200, 403, 404]
            
            # Should not expose other users' data
            if response.status_code == 200:
                data = response.get_json()
                if data.get('id') != self.test_user.id and data.get('id') != 1:
                    pytest.fail(f"User ID injection exposed other users: {payload}")


class TestXSSVulnerabilities:
    """Test Cross-Site Scripting vulnerabilities."""
    
    def setup_method(self):
        """Setup test environment."""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.test_user = User(
            username='testuser',
            email='test@example.com',
            password_hash=hash_password('TestPass123!')
        )
        db.session.add(self.test_user)
        db.session.commit()
        
        self.token = generate_token(self.test_user.id)
    
    def teardown_method(self):
        """Cleanup after tests."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_post_content_xss(self):
        """Test XSS in post content creation."""
        headers = {'Authorization': f'Bearer {self.token}'}
        
        xss_payloads = [
            '<script>alert("XSS")</script>',
            '<img src="x" onerror="alert(\'XSS\')">',
            '<svg onload="alert(\'XSS\')">',
            'javascript:alert(\'XSS\')',
            '<body onload=alert(\'XSS\')>',
            '<iframe src="javascript:alert(\'XSS\')">',
            '<a href="javascript:alert(\'XSS\')">Click</a>',
            '<div style="background:url(javascript:alert(\'XSS\'))">',
            '<table background="javascript:alert(\'XSS\')">',
            '"><script>alert(\'XSS\')</script>',
            '\'><script>alert(\'XSS\')</script>',
        ]
        
        for payload in xss_payloads:
            response = self.client.post('/api/posts', json={
                'title': 'Test Post',
                'content': f'Normal text {payload} more text'
            }, headers=headers)
            
            assert response.status_code == 201
            
            data = response.get_json()
            post_id = data['id']
            
            # Retrieve the post
            response = self.client.get(f'/api/posts/{post_id}', headers=headers)
            assert response.status_code == 200
            
            post_data = response.get_json()
            content = post_data['content']
            
            # Check if script tags are sanitized
            if '<script>' in content.lower() or 'javascript:' in content.lower():
                # Script tags should be escaped or removed
                if not ('&lt;script&gt;' in content or '&lt;/script&gt;' in content):
                    pytest.fail(f"XSS vulnerability detected in post content: {payload}")
            
            # Check for other dangerous tags
            dangerous_patterns = [
                r'onerror\s*=',
                r'onload\s*=',
                r'onclick\s*=',
                r'onmouseover\s*=',
                r'javascript:',
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    # Should be escaped
                    if not ('&' in content and ';' in content):
                        pytest.fail(f"XSS attribute vulnerability: {pattern} in {content}")
    
    def test_comment_xss(self):
        """Test XSS in comments."""
        headers = {'Authorization': f'Bearer {self.token}'}
        
        # Create a post first
        post_response = self.client.post('/api/posts', json={
            'title': 'Test Post for Comments',
            'content': 'Test content'
        }, headers=headers)
        post_id = post_response.get_json()['id']
        
        xss_payloads = [
            '<script>alert("Comment XSS")</script>',
            '<img src="x" onerror="stealCookies()">',
        ]
        
        for payload in xss_payloads:
            response = self.client.post(f'/api/posts/{post_id}/comments', json={
                'content': payload
            }, headers=headers)
            
            assert response.status_code == 201
            
            data = response.get_json()
            comment_id = data['id']
            
            # Retrieve comment
            response = self.client.get(f'/api/comments/{comment_id}', headers=headers)
            assert response.status_code == 200
            
            comment_data = response.get_json()
            content = comment_data['content']
            
            # Check for sanitization
            if '<script>' in content:
                if not content.startswith('&lt;script&gt;'):
                    pytest.fail(f"XSS in comment not sanitized: {payload}")
    
    def test_username_xss(self):
        """Test XSS in username field."""
        headers = {'Authorization': f'Bearer {self.token}'}
        
        xss_payload = '<script>alert(1)</script>'
        
        # Try to update username with XSS payload
        response = self.client.put('/api/users/profile', json={
            'username': xss_payload,
            'email': 'test@example.com'
        }, headers=headers)
        
        # Should either reject or sanitize
        if response.status_code == 200:
            data = response.get_json()
            username = data['username']
            
            # Check if sanitized
            if '<script>' in username:
                pytest.fail(f"XSS in username field not sanitized: {username}")
    
    def test_json_response_xss(self):
        """Test XSS through JSON responses with Content-Type manipulation."""
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'text/html'  # Try to force HTML response
        }
        
        response = self.client.get('/api/users/me', headers=headers)
        
        # Check Content-Type
        content_type = response.headers.get('Content-Type', '')
        
        # Should be application/json, not text/html
        if 'text/html' in content_type:
            # Check if JSON is being interpreted as HTML
            body = response.get_data(as_text=True)
            if '<script>' in body:
                pytest.fail("JSON API returning HTML with potential XSS")
        
        # Also test with X-Requested-With header
        headers['X-Requested-With'] = 'XMLHttpRequest'
        response = self.client.get('/api/users/me', headers=headers)
        
        # Should still return JSON
        assert 'application/json' in response.headers.get('Content-Type', '')


class TestCSRFVulnerabilities:
    """Test Cross-Site Request Forgery vulnerabilities."""
    
    def setup_method(self):
        """Setup test environment."""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.test_user = User(
            username='testuser',
            email='test@example.com',
            password_hash=hash_password('TestPass123!')
        )
        db.session.add(self.test_user)
        db.session.commit()
        
        self.token = generate_token(self.test_user.id)
    
    def teardown_method(self):
        """Cleanup after tests."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_csrf_token_required(self):
        """Test that CSRF tokens are required for state-changing operations."""
        # First login to get session cookie
        login_response = self.client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'TestPass123!'
        })
        
        # Get session cookie
        cookies = login_response.headers.get_all('Set-Cookie')
        session_cookie = None
        for cookie in cookies:
            if 'session' in cookie.lower():
                session_cookie = cookie.split(';')[0]
        
        if session_cookie:
            # Try to make a POST request without CSRF token
            headers = {
                'Cookie': session_cookie,
                'Content-Type': 'application/json'
            }
            
            # Test password change without CSRF token
            response = self.client.post('/api/users/change-password', json={
                'current_password': 'TestPass123!',
                'new_password': 'NewPass123!'
            }, headers=headers)
            
            # Should require CSRF token
            if response.status_code == 200:
                # Check if CSRF protection is enabled
                # Look for CSRF token in forms or headers requirement
                pytest.fail("CSRF protection missing: Password change allowed without CSRF token")
    
    def test_same_origin_policy(self):
        """Test Same-Origin Policy bypass attempts."""
        headers = {'Authorization': f'Bearer {self.token}'}
        
        # Test with different Origin headers
        origins = [
            'https://evil.com',
            'http://attacker.com',
            'null',
            'https://trusted.com.evil.com',
        ]
        
        for origin in origins:
            headers['Origin'] = origin
            
            response = self.client.post('/api/posts', json={
                'title': 'CSRF Test',
                'content': 'Test content'
            }, headers=headers)
            
            # Check for CORS headers
            cors_headers = response.headers.get('Access-Control-Allow-Origin', '')
            
            if origin in cors_headers and origin != self.app.config.get('ALLOWED_ORIGINS', ''):
                pytest.fail(f"CORS misconfiguration allowing origin: {origin}")
    
    def test_custom_header_bypass(self):
        """Test CSRF bypass using custom headers."""
        # Some APIs check for custom headers that can't be set cross-origin
        headers = {'Authorization': f'Bearer {self.token}'}
        
        # Try without X-Requested-With header
        response = self.client.post('/api/posts', json={
            'title': 'Test',
            'content': 'Content'
        }, headers=headers)
        
        # Note: This test documents the behavior, doesn't necessarily fail
        # Many APIs require X-Requested-With: XMLHttpRequest
        
        if response.status_code == 200:
            # Try again with the header
            headers['X-Requested-With'] = 'XMLHttpRequest'
            response2 = self.client.post('/api/posts', json={
                'title': 'Test2',
                'content': 'Content2'
            }, headers=headers)
            
            # Both should work or both should fail
            if response.status_code != response2.status_code:
                pytest.warn("Inconsistent CSRF protection with X-Requested-With header")


class TestAuthenticationBypass:
    """Test authentication and authorization bypass vulnerabilities."""
    
    def setup_method(self):
        """Setup test environment."""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Create regular user
        self.regular_user = User(
            username='regular',
            email='regular@example.com',
            password_hash=hash_password('RegularPass123!'),
            role='user'
        )
        
        # Create admin user
        self.admin_user = User(
            username='admin',
            email='admin@example.com',
            password_hash=hash_password('AdminPass123!'),
            role='admin'
        )
        
        db.session.add_all([self.regular_user, self.admin_user])
        db.session.commit()
        
        self.regular_token = generate_token(self.regular_user.id)
        self.admin_token = generate_token(self.admin_user.id)
    
    def teardown_method(self):
        """Cleanup after tests."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_jwt_tampering(self):
        """Test JWT token tampering vulnerabilities."""
        # Test 1: None algorithm attack
        headers = {'alg': 'none'}
        payload = {'user_id': self.admin_user.id, 'role': 'admin'}
        
        # Create a token with none algorithm (should be rejected)
        import base64
        import json as json_module
        
        header_b64 = base64.urlsafe_b64encode(
            json_module.dumps(headers).encode()
        ).decode().rstrip('=')
        
        payload_b64 = base64.urlsafe_b64encode(
            json_module.dumps(payload).encode()
        ).decode().rstrip('=')
        
        none_token = f"{header_b64}.{payload_b64}."
        
        response = self.client.get('/api/admin/users', 
                                 headers={'Authorization': f'Bearer {none_token}'})
        
        # Should reject none algorithm
        if response.status_code == 200:
            pytest.fail("JWT none algorithm vulnerability")
        
        # Test 2: HMAC vs RSA confusion
        # Try to use HS256 with public key
        # (This would require actual crypto testing, simplified here)
        
        # Test 3: Expired token
        expired_payload = {
            'user_id': self.regular_user.id,
            'exp': datetime.utcnow() - timedelta(hours=1)
        }
        # In practice, we'd need to generate a real expired token
        # This test documents the