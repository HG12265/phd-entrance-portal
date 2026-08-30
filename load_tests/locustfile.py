import random
import queue
import gevent
from locust import HttpUser, task, SequentialTaskSet, between
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

"""
LOCUST LOAD TESTING SCENARIOS FOR PHD ENTRANCE PORTAL
===================================================

IMPORTANT SECURITY & SAFETY WARNING:
------------------------------------
1. NEVER run load tests against the real production database during the exam day.
2. Ensure you have backed up the database before running stress simulations.
3. Use test candidates and test exam sessions only.
4. Target hosts must be set to the server IP/URL of the test instance.

Recommended Execution Configurations:
-------------------------------------
1. Smoke Test (Verify functionality under load):
   locust -f load_tests/locustfile.py --users 50 --spawn-rate 5 --host=http://localhost

2. Production Simulation (Scale up to expected load):
   locust -f load_tests/locustfile.py --users 250 --spawn-rate 10 --host=http://localhost

3. Stress Test (Find breaking point of the server specs):
   locust -f load_tests/locustfile.py --users 300 --spawn-rate 15 --host=http://localhost
"""

# Global synchronization variables
spawned_users = 0
start_barrier = gevent.event.Event()

from locust import events

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global spawned_users
    spawned_users = 0
    start_barrier.clear()
    print("----- New Load Test Started: Resetting spawn counter -----")

class CandidateExamSimulation(SequentialTaskSet):
    
    def on_start(self):
        """Simulates candidate launching the exam portal and logging in."""
        global spawned_users
        
        # Disable SSL verification for self-signed certificates
        self.client.verify = False
        
        self.headers = {}
        self.candidate_id = None
        self.attempt_id = None
        self.question_ids = []
        
        # Fetch a unique candidate number from the shared queue to prevent collision-induced device locks (423)
        try:
            candidate_num = self.user.candidate_queue.get_nowait()
        except (AttributeError, queue.Empty):
            candidate_num = random.randint(1, 600)
            
        self.app_number = f"CET/PHD/TEST/{candidate_num:04d}"
        self.dob = "01-01-2004"  # Default DOB for test candidates

        # Increment spawned count and synchronize all virtual users
        spawned_users += 1
        
        runner = self.user.environment.runner
        target_users = runner.target_user_count if runner else 350
        
        print(f"[Locust] Spawning user: {spawned_users} / {target_users} ({self.app_number})")
        
        if spawned_users >= target_users:
            print(f"[Locust] Target of {target_users} users reached! Releasing the barrier to log in simultaneously...")
            start_barrier.set()
            
        # Wait for all expected concurrent users to spawn before sending the login requests
        start_barrier.wait()

        # 1. Post Login
        with self.client.post("/api/candidate/auth/login", json={
            "application_number": self.app_number,
            "dob": self.dob
        }, catch_response=True) as response:
            if response.status_code == 200:
                res_data = response.json()
                token = res_data.get("access_token")
                self.candidate_id = res_data.get("candidate", {}).get("id")
                
                # Mock unique client fingerprint to satisfy device lock checks
                import uuid
                self.headers = {
                    "Authorization": f"Bearer {token}",
                    "X-Exam-Client-Id": str(uuid.uuid4())
                }
                response.success()
                print(f"[Locust] Login success for {self.app_number}")
            else:
                response.failure(f"Login failed: status={response.status_code}")
                print(f"[Locust] Login FAILED for {self.app_number}: status={response.status_code}")
                self.idle_forever()

    def idle_forever(self):
        """Keeps the virtual candidate user alive but idle to prevent Locust from spawning replacements."""
        while True:
            gevent.sleep(3600)

    @task
    def fetch_profile(self):
        """Simulates student viewing Candidate Profile details."""
        if not self.headers:
            return
        self.client.get("/api/candidate/auth/me", headers=self.headers)

    @task
    def check_instructions_status(self):
        """Simulates student waiting on instructions screen and checking session details."""
        if not self.headers:
            return
        # Fetch exam session details
        self.client.get("/api/candidate/exam-status", headers=self.headers)

    @task
    def enter_lock_guard(self):
        """Simulates clicking 'Enter Exam' locking guard check."""
        if not self.headers:
            return
        with self.client.post("/api/candidate/exam/enter", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to enter lock guard: status={response.status_code}")
                self.idle_forever()

    @task
    def start_exam_attempt(self):
        """Simulates student starting the exam (fetches and shuffles questions)."""
        if not self.headers:
            return
        with self.client.post("/api/candidate/exam/start", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                res_data = response.json()
                self.attempt_id = res_data.get("attempt_id")
                self.question_ids = [q.get("question_id") for q in res_data.get("questions", [])]
                response.success()
            else:
                response.failure(f"Failed to start exam: status={response.status_code}")
                self.idle_forever()

    @task
    def load_current_exam_room(self):
        """Simulates candidate reloading browser (Timer sync & restore state)."""
        if not self.headers:
            return
        self.client.get("/api/candidate/exam/current", headers=self.headers)

    @task
    def save_answers_loop(self):
        """Simulates student choosing options in a loop (up to 70 saves)."""
        if not self.headers or not self.attempt_id or not self.question_ids:
            return
            
        # Simulate student progress: saving answers to a random subset of questions
        save_count = min(len(self.question_ids), random.randint(50, 70))
        sampled_questions = random.sample(self.question_ids, save_count)
        
        for q_id in sampled_questions:
            # Simulate student picking options A, B, C, or D
            selected_option = random.choice(["A", "B", "C", "D"])
            self.client.post("/api/candidate/exam/save-answer", json={
                "attempt_id": self.attempt_id,
                "question_id": q_id,
                "selected_option": selected_option
            }, headers=self.headers)
            
            # Simulate delay between answer changes (e.g. 0.2 to 0.5 seconds for fast load testing)
            gevent.sleep(random.uniform(0.2, 0.5))

    @task
    def sync_timer(self):
        """Simulates automated background resync of student clock."""
        if not self.headers or not self.attempt_id:
            return
        self.client.get(f"/api/candidate/exam/timer/{self.attempt_id}", headers=self.headers)

    @task
    def submit_exam_attempt(self):
        """Simulates student manually submitting their exam at the end."""
        if not self.headers or not self.attempt_id:
            return
        with self.client.post("/api/candidate/exam/submit", json={
            "attempt_id": self.attempt_id,
            "submission_type": "manual"
        }, headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to submit: status={response.status_code}")
        
        # Stop candidate actions after submit by idling forever (no looping/re-login)
        self.idle_forever()

class LoadTestCandidate(HttpUser):
    tasks = [CandidateExamSimulation]
    wait_time = between(1, 3)

    # Queue of candidate indices from 1 to 600 to ensure completely unique logins per user
    candidate_queue = queue.Queue()
    for i in range(1, 601):
        candidate_queue.put(i)
