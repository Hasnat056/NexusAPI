"""
locustfile.py
-------------
Load testing for the University LMS backend using Locust.

Three user classes representing three scenarios:

1. NormalLoadUser     — 200 users, sustained read-heavy traffic (normal day)
2. PeakLoadUser       — 1000 users, mixed read/write (registration peak)
3. SpikeUser          — ramps to 5000 users rapidly (worst-case spike)

Run scenarios individually:

  Normal load (200 users, 10 min):
    locust -f locustfile.py NormalLoadUser --headless -u 200 -r 20 --run-time 10m --host http://localhost:8000

  Peak load (1000 users, 5 min):
    locust -f locustfile.py PeakLoadUser --headless -u 1000 -r 50 --run-time 5m --host http://localhost:8000

  Spike test (ramp to 5000 in 60s):
    locust -f locustfile.py SpikeUser --headless -u 5000 -r 250 --run-time 3m --host http://localhost:8000

  All together with UI:
    locust -f locustfile.py --host http://localhost:8000
    → open http://localhost:8089 in browser

Install:
    pip install locust
"""

import random
import json
from locust import HttpUser, task, between, events
from locust.exception import StopUser


# ---------------------------------------------------------------------------
# Shared credentials — update these to match your test database
# ---------------------------------------------------------------------------

ADMIN_CREDENTIALS = {
    'username': 'rhays056@gmail.com',
    'password': 'admin12345678',
}

FACULTY_CREDENTIALS = {
    'username': 'faculty@test.com',
    'password': 'facultypass123',
}

STUDENT_CREDENTIALS = {
    'username': 'student@test.com',
    'password': 'studentpass123',
}

BASE = '/api/admin'


# ---------------------------------------------------------------------------
# Base class — handles authentication
# ---------------------------------------------------------------------------

class AuthenticatedUser(HttpUser):
    abstract = True
    token = None

    def on_start(self):
        """Authenticate and store JWT token before running tasks."""
        self.token = self._login(self.credentials)
        if not self.token:
            raise StopUser()
        self.client.headers.update({'Authorization': f'Bearer {self.token}'})

    def _login(self, credentials):
        with self.client.post(
            '/api/token/',
            json=credentials,
            catch_response=True,
            name='POST /api/token/ [auth]'
        ) as response:
            if response.status_code == 200:
                return response.json().get('access')
            else:
                response.failure(f'Login failed: {response.status_code}')
                return None


# ---------------------------------------------------------------------------
# Scenario 1: Normal Load
# Simulates a regular day — mostly reads, occasional writes
# Target: 200 concurrent users, sustained 10 minutes
# ---------------------------------------------------------------------------

class NormalLoadUser(AuthenticatedUser):
    """
    Mixed admin/faculty/student behavior on a normal day.
    Heavily read-biased — 80% reads, 20% writes.
    """
    wait_time = between(2, 5)  # realistic think time between actions
    credentials = ADMIN_CREDENTIALS

    @task(5)
    def view_dashboard(self):
        """Most common action — cached after first hit."""
        self.client.get(f'{BASE}/dashboard/', name='GET /dashboard/')

    @task(4)
    def list_faculty(self):
        self.client.get(f'{BASE}/faculty/', name='GET /faculty/')

    @task(4)
    def list_students(self):
        self.client.get(f'{BASE}/students/', name='GET /students/')

    @task(3)
    def list_courses(self):
        self.client.get(f'{BASE}/courses/', name='GET /courses/')

    @task(3)
    def list_semesters(self):
        self.client.get(f'{BASE}/semesters/', name='GET /semesters/')

    @task(3)
    def list_allocations(self):
        self.client.get(f'{BASE}/allocations/', name='GET /allocations/')

    @task(3)
    def list_enrollments(self):
        self.client.get(f'{BASE}/enrollments/', name='GET /enrollments/')

    @task(2)
    def list_classes(self):
        self.client.get(f'{BASE}/classes/', name='GET /classes/')

    @task(2)
    def list_departments(self):
        self.client.get(f'{BASE}/departments/', name='GET /departments/')

    @task(2)
    def list_programs(self):
        self.client.get(f'{BASE}/programs/', name='GET /programs/')

    @task(1)
    def search_faculty(self):
        """Search bypasses cache — tests DB query performance."""
        query = random.choice(['Ahmed', 'Ali', 'Hassan', 'CS', 'Lecturer'])
        self.client.get(
            f'{BASE}/faculty/?search={query}',
            name='GET /faculty/?search='
        )

    @task(1)
    def search_students(self):
        query = random.choice(['BSCS', 'Active', '2022', '2023'])
        self.client.get(
            f'{BASE}/students/?search={query}',
            name='GET /students/?search='
        )

    @task(1)
    def filter_allocations_by_semester(self):
        """Filtered queries test index performance."""
        self.client.get(
            f'{BASE}/allocations/?status=Ongoing',
            name='GET /allocations/?status=Ongoing'
        )

    @task(1)
    def filter_enrollments_by_status(self):
        self.client.get(
            f'{BASE}/enrollments/?status=Active',
            name='GET /enrollments/?status=Active'
        )


# ---------------------------------------------------------------------------
# Scenario 2: Peak Load
# Simulates registration day — heavy writes mixed with reads
# Target: 1000 concurrent users, 5 minutes
# ---------------------------------------------------------------------------

class PeakLoadUser(AuthenticatedUser):
    """
    Registration-day behavior.
    Mixed reads and writes — enrollment creation, allocation creation.
    Tests DB write throughput and serializer performance under load.
    """
    wait_time = between(1, 3)  # less think time — users are in a hurry
    credentials = ADMIN_CREDENTIALS

    # IDs populated dynamically during on_start
    semester_id = None
    allocation_id = None
    student_id = None

    def on_start(self):
        super().on_start()
        self._fetch_ids()

    def _fetch_ids(self):
        """Fetch existing IDs to use in write operations."""
        r = self.client.get(f'{BASE}/semesters/', name='[setup] GET /semesters/')
        if r.status_code == 200 and r.json().get('results'):
            self.semester_id = r.json()['results'][0]['semester_id']

        r = self.client.get(
            f'{BASE}/allocations/?status=Ongoing',
            name='[setup] GET /allocations/?status=Ongoing'
        )
        if r.status_code == 200 and r.json().get('results'):
            self.allocation_id = r.json()['results'][0]['allocation_id']

        r = self.client.get(f'{BASE}/students/', name='[setup] GET /students/')
        if r.status_code == 200 and r.json().get('results'):
            results = r.json()['results']
            self.student_id = results[random.randint(0, len(results)-1)]['person']['person_id'] if results else None

    @task(4)
    def view_dashboard(self):
        self.client.get(f'{BASE}/dashboard/', name='GET /dashboard/')

    @task(3)
    def list_enrollments(self):
        self.client.get(f'{BASE}/enrollments/', name='GET /enrollments/')

    @task(3)
    def list_allocations(self):
        self.client.get(f'{BASE}/allocations/', name='GET /allocations/')

    @task(2)
    def list_students(self):
        self.client.get(f'{BASE}/students/', name='GET /students/')

    @task(2)
    def create_enrollment(self):
        """Concurrent enrollment creation — tests write contention."""
        if not self.allocation_id or not self.student_id:
            return
        with self.client.post(
            f'{BASE}/enrollments/',
            json={
                'student_id': self.student_id,
                'allocation_id': self.allocation_id,
            },
            catch_response=True,
            name='POST /enrollments/'
        ) as response:
            if response.status_code in (201, 400):
                # 400 is acceptable — duplicate enrollment, invalid data
                response.success()
            else:
                response.failure(f'Unexpected status: {response.status_code}')

    @task(1)
    def view_semester_detail(self):
        if not self.semester_id:
            return
        self.client.get(
            f'{BASE}/semesters/{self.semester_id}/',
            name='GET /semesters/<id>/'
        )

    @task(1)
    def filter_enrollments_by_student(self):
        if not self.student_id:
            return
        self.client.get(
            f'{BASE}/enrollments/?student_id={self.student_id}',
            name='GET /enrollments/?student_id='
        )

    @task(1)
    def paginate_through_faculty(self):
        """Tests pagination performance under load."""
        page = random.randint(1, 3)
        self.client.get(
            f'{BASE}/faculty/?page={page}',
            name='GET /faculty/?page='
        )


# ---------------------------------------------------------------------------
# Scenario 3: Spike Test
# Sudden burst — simulates viral event or system recovery after downtime
# Target: ramp to 5000 users in 60 seconds
# ---------------------------------------------------------------------------

class SpikeUser(AuthenticatedUser):
    """
    Worst-case spike scenario.
    Minimal think time — hammers the most common endpoints.
    Goal: find the breaking point, not achieve 100% success rate.
    Watch for: response time degradation, 500 errors, DB connection exhaustion.
    """
    wait_time = between(0.5, 1.5)  # very little think time
    credentials = ADMIN_CREDENTIALS

    @task(6)
    def dashboard_spike(self):
        """
        Dashboard is cached — should handle spike well.
        If it doesn't, cache layer is the bottleneck.
        """
        with self.client.get(
            f'{BASE}/dashboard/',
            catch_response=True,
            name='GET /dashboard/ [spike]'
        ) as response:
            if response.elapsed.total_seconds() > 2.0:
                response.failure(f'Too slow: {response.elapsed.total_seconds():.2f}s')
            elif response.status_code != 200:
                response.failure(f'Status: {response.status_code}')

    @task(4)
    def faculty_list_spike(self):
        """Cached list — should absorb spike. Tests Redis under concurrent reads."""
        with self.client.get(
            f'{BASE}/faculty/',
            catch_response=True,
            name='GET /faculty/ [spike]'
        ) as response:
            if response.elapsed.total_seconds() > 3.0:
                response.failure(f'Too slow: {response.elapsed.total_seconds():.2f}s')

    @task(4)
    def student_list_spike(self):
        with self.client.get(
            f'{BASE}/students/',
            catch_response=True,
            name='GET /students/ [spike]'
        ) as response:
            if response.elapsed.total_seconds() > 3.0:
                response.failure(f'Too slow: {response.elapsed.total_seconds():.2f}s')

    @task(3)
    def enrollment_list_spike(self):
        with self.client.get(
            f'{BASE}/enrollments/',
            catch_response=True,
            name='GET /enrollments/ [spike]'
        ) as response:
            if response.elapsed.total_seconds() > 3.0:
                response.failure(f'Too slow: {response.elapsed.total_seconds():.2f}s')

    @task(2)
    def auth_spike(self):
        """
        Concurrent token generation — tests JWT signing throughput.
        This is CPU-bound — will degrade under spike faster than cached reads.
        """
        with self.client.post(
            '/api/token/',
            json=ADMIN_CREDENTIALS,
            catch_response=True,
            name='POST /api/token/ [spike]'
        ) as response:
            if response.elapsed.total_seconds() > 2.0:
                response.failure(f'Auth too slow: {response.elapsed.total_seconds():.2f}s')
            elif response.status_code == 200:
                # refresh token for continued requests
                self.token = response.json().get('access')
                self.client.headers.update({'Authorization': f'Bearer {self.token}'})

    @task(1)
    def uncached_search_spike(self):
        """
        Search bypasses cache — hits DB directly.
        Under spike this will cause DB connection exhaustion first.
        """
        query = random.choice(['Ahmed', 'Ali', 'CS', 'Active', '2024'])
        with self.client.get(
            f'{BASE}/students/?search={query}',
            catch_response=True,
            name='GET /students/?search= [spike]'
        ) as response:
            if response.elapsed.total_seconds() > 5.0:
                response.failure(f'Search too slow: {response.elapsed.total_seconds():.2f}s')


# ---------------------------------------------------------------------------
# Event hooks — print summary thresholds after test
# ---------------------------------------------------------------------------

@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """Print pass/fail thresholds after test completes."""
    stats = environment.stats.total

    print("\n" + "="*60)
    print("LOAD TEST SUMMARY")
    print("="*60)
    print(f"Total requests      : {stats.num_requests}")
    print(f"Failed requests     : {stats.num_failures}")
    print(f"Failure rate        : {stats.fail_ratio * 100:.1f}%")
    print(f"Avg response time   : {stats.avg_response_time:.0f}ms")
    print(f"95th percentile     : {stats.get_response_time_percentile(0.95):.0f}ms")
    print(f"99th percentile     : {stats.get_response_time_percentile(0.99):.0f}ms")
    print(f"Requests/sec        : {stats.current_rps:.1f}")
    print("="*60)

    # Thresholds — adjust based on your SLA
    FAIL_RATE_THRESHOLD = 0.05        # max 5% failure rate
    AVG_RESPONSE_THRESHOLD = 1000     # max 1000ms average
    P95_RESPONSE_THRESHOLD = 3000     # max 3000ms at 95th percentile

    passed = True
    if stats.fail_ratio > FAIL_RATE_THRESHOLD:
        print(f"FAIL: Failure rate {stats.fail_ratio*100:.1f}% exceeds {FAIL_RATE_THRESHOLD*100}%")
        passed = False
    if stats.avg_response_time > AVG_RESPONSE_THRESHOLD:
        print(f"FAIL: Avg response {stats.avg_response_time:.0f}ms exceeds {AVG_RESPONSE_THRESHOLD}ms")
        passed = False
    if stats.get_response_time_percentile(0.95) > P95_RESPONSE_THRESHOLD:
        print(f"FAIL: P95 {stats.get_response_time_percentile(0.95):.0f}ms exceeds {P95_RESPONSE_THRESHOLD}ms")
        passed = False

    if passed:
        print("RESULT: PASSED — all thresholds met")
    else:
        print("RESULT: FAILED — system does not meet performance requirements")
        environment.process_exit_code = 1