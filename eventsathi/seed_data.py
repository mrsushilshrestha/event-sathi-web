"""
Seed demo events for EventSathi.
Run: python manage.py shell < seed_data.py
"""
import os
import sys
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventsathi.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from events.models import Event, TicketTier, Speaker, EventSession, Sponsor, Announcement

rahul = User.objects.get(username='rahul')
admin = User.objects.get(username='admin')

events_data = [
    {
        'title': 'TechFest 2024 - India\'s Largest Tech Summit',
        'slug': 'techfest-2024',
        'description': '''TechFest 2024 is India's premier technology summit bringing together the brightest minds in AI, blockchain, cloud computing, and emerging technologies.

Join 2000+ tech enthusiasts, industry leaders, and innovators for 2 days of keynotes, workshops, hackathons, and unparalleled networking opportunities.

Whether you are a student, developer, entrepreneur, or investor — TechFest 2024 has something for everyone.''',
        'category': 'conference',
        'start_date': timezone.now() + timedelta(days=30),
        'end_date': timezone.now() + timedelta(days=32),
        'venue': 'Jawaharlal Nehru Stadium',
        'city': 'New Delhi',
        'max_capacity': 2000,
        'status': 'published',
        'is_featured': True,
        'tags': 'AI, Blockchain, Cloud, IoT, Machine Learning, Startups',
        'organizer': rahul,
    },
    {
        'title': 'Design Sprint: UX & Product Workshop',
        'slug': 'design-sprint-ux-workshop',
        'description': '''A hands-on 2-day design sprint workshop for product designers, UX researchers, and product managers.

Learn Google's famous Design Sprint methodology, conduct real user research, and prototype solutions to real problems.

Limited to 50 participants for an intimate, high-impact learning experience.''',
        'category': 'workshop',
        'start_date': timezone.now() + timedelta(days=15),
        'end_date': timezone.now() + timedelta(days=16),
        'venue': 'WeWork Prestige Central',
        'city': 'Bengaluru',
        'max_capacity': 50,
        'status': 'published',
        'is_featured': True,
        'tags': 'UX, Design, Product, Sprint, Figma',
        'organizer': admin,
    },
    {
        'title': 'StartupHive Demo Day 2024',
        'slug': 'startuphive-demo-day-2024',
        'description': '''Watch 20 of India's most promising startups pitch to a panel of top VCs and angel investors.

StartupHive Demo Day connects founders with funding. Join as an investor, mentor, or enthusiast to witness the future of Indian tech entrepreneurship.

Sectors: FinTech, EdTech, HealthTech, AgriTech, CleanTech.''',
        'category': 'networking',
        'start_date': timezone.now() + timedelta(days=45),
        'end_date': timezone.now() + timedelta(days=45),
        'venue': 'T-Hub Innovation Campus',
        'city': 'Hyderabad',
        'max_capacity': 300,
        'status': 'published',
        'is_featured': False,
        'is_virtual': True,
        'virtual_link': 'https://meet.google.com/demo-day',
        'tags': 'Startup, VC, Funding, Demo Day, Pitch',
        'organizer': rahul,
    },
    {
        'title': 'AI & Machine Learning Symposium',
        'slug': 'ai-ml-symposium-2024',
        'description': '''A full-day deep dive into the state of AI and machine learning in 2024.

Topics include: Large Language Models, Generative AI, Responsible AI, AI in Healthcare, and Real-world ML deployment.

Featuring researchers from IITs, IISc, and global tech companies.''',
        'category': 'seminar',
        'start_date': timezone.now() + timedelta(days=20),
        'end_date': timezone.now() + timedelta(days=20),
        'venue': 'IIT Bombay Campus',
        'city': 'Mumbai',
        'max_capacity': 500,
        'status': 'published',
        'tags': 'AI, ML, LLM, Generative AI, Research',
        'organizer': admin,
    },
]

created_events = []
for ed in events_data:
    ev, created = Event.objects.get_or_create(slug=ed['slug'], defaults=ed)
    if created:
        print(f'Created event: {ev.title}')
    created_events.append(ev)

# Add ticket tiers to first event
ev1 = created_events[0]
if not ev1.ticket_tiers.exists():
    TicketTier.objects.create(event=ev1, name='Early Bird', price=999, capacity=500, description='Limited early bird seats at a special price.', benefits='Entry to all sessions\nConference kit\nLunch & snacks\nNetworking dinner')
    TicketTier.objects.create(event=ev1, name='General', price=1999, capacity=1200, description='Standard conference pass.', benefits='Entry to all sessions\nConference kit\nLunch & snacks')
    TicketTier.objects.create(event=ev1, name='VIP', price=4999, capacity=100, description='Premium VIP experience with exclusive access.', benefits='VIP lounge access\nSpeaker meet & greet\nFront-row seating\nAll General benefits\nExclusive VIP dinner')

    # Speakers
    s1 = Speaker.objects.create(event=ev1, name='Dr. Aisha Kapoor', designation='Head of AI Research', organization='Google India', bio='Dr. Kapoor leads AI research initiatives at Google India with 15+ years of ML experience.', abstract='Keynote: The Future of Large Language Models in the Indian Context')
    s2 = Speaker.objects.create(event=ev1, name='Rohan Mehta', designation='Co-founder & CTO', organization='PhonePe', bio='Rohan built the payments infrastructure powering 500M+ UPI transactions daily.', abstract='Building Fintech at Scale: Engineering Lessons from PhonePe')
    s3 = Speaker.objects.create(event=ev1, name='Priya Nair', designation='VP Product', organization='Zomato', bio='Priya leads product strategy for Hyperpure and B2B business at Zomato.', abstract='From Chaos to Clarity: Product Decisions at Hyper Scale')

    # Sessions
    base_dt = ev1.start_date.replace(hour=9, minute=0, second=0)
    sess1 = EventSession.objects.create(event=ev1, title='Opening Keynote: AI in 2024', speaker=s1, track='keynote', room='Main Auditorium', start_time=base_dt, end_time=base_dt+timedelta(hours=1), description='A deep dive into where AI is headed and what it means for India.')
    sess2 = EventSession.objects.create(event=ev1, title='Building Fintech at Scale', speaker=s2, track='technical', room='Hall A', start_time=base_dt+timedelta(hours=1,minutes=30), end_time=base_dt+timedelta(hours=2,minutes=30), description='Engineering lessons from building India\'s largest digital payments platform.')
    sess3 = EventSession.objects.create(event=ev1, title='Product @ Hyper Scale', speaker=s3, track='main', room='Hall B', start_time=base_dt+timedelta(hours=3), end_time=base_dt+timedelta(hours=4), description='How product decisions are made when millions depend on your app.')
    sess4 = EventSession.objects.create(event=ev1, title='Networking Lunch & Exhibition', track='networking', room='Exhibition Hall', start_time=base_dt+timedelta(hours=4), end_time=base_dt+timedelta(hours=5))
    sess5 = EventSession.objects.create(event=ev1, title='AI Workshop: Build Your First LLM App', speaker=s1, track='workshop', room='Lab 1', start_time=base_dt+timedelta(hours=5), end_time=base_dt+timedelta(hours=7), description='Hands-on workshop building a production LLM app with LangChain and OpenAI.')

    # Sponsors
    Sponsor.objects.create(event=ev1, name='Google', tier='platinum', website='https://google.com', description='Platinum sponsor — main stage sponsor for TechFest 2024')
    Sponsor.objects.create(event=ev1, name='Microsoft', tier='gold', website='https://microsoft.com', description='Azure cloud infrastructure partner')
    Sponsor.objects.create(event=ev1, name='PhonePe', tier='gold', website='https://phonepe.com', description='FinTech track sponsor')
    Sponsor.objects.create(event=ev1, name='GitHub', tier='silver', website='https://github.com', description='Developer tools partner')
    Sponsor.objects.create(event=ev1, name='AWS', tier='silver', website='https://aws.amazon.com', description='Cloud computing partner')

    # Announcements
    Announcement.objects.create(event=ev1, author=rahul, title='Registration Now Open!', content='Grab your Early Bird tickets before December 31st. Over 500 tickets sold in the first week!', priority='important')
    Announcement.objects.create(event=ev1, author=rahul, title='Speaker Lineup Announced', content='We are thrilled to announce our first batch of speakers including Dr. Aisha Kapoor from Google and Rohan Mehta from PhonePe!', priority='normal')

# Workshop event ticket tiers
ev2 = created_events[1]
if not ev2.ticket_tiers.exists():
    TicketTier.objects.create(event=ev2, name='Participant', price=2500, capacity=50, description='Full 2-day design sprint workshop with materials.', benefits='Workshop materials kit\nCertificate of completion\nLunch both days\nMentorship session')

print('Seed data created successfully!')
