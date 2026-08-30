import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Globe, Mail, Phone, Code, Cpu } from 'lucide-react';

export default function DeveloperInfo() {
  const navigate = useNavigate();

  const developers = [
    {
      name: 'GOWTHAM G',
      degree: 'MCA',
      role: 'FULL STACK DEVELOPER',
      skills: ['REACT', 'TAILWIND CSS', 'MONGODB', 'MYSQL', 'PYTHON', 'NODE JS', 'DOCKER'],
      portfolio: 'https://itsgowtham.vercel.app',
      email: 'gowtham114411@gmail.com',
      phone: '+91 93442 32465',
      image: "/image.png"
    },
    {
      name: 'SAM B',
      degree: 'MCA',
      role: 'FULL STACK DEVELOPER',
      skills: ['REACT', 'NODE JS', 'MONGODB', 'MYSQL', 'PYTHON', 'DOCKER'],
      portfolio: 'https://bsamportfolio.netlify.app',
      email: 'bsam53888@gmail.com',
      phone: '+91 81227 55346',
      image: "/sam.png"
    }
  ];

  return (
    <div className="page-container" style={{ maxWidth: '1100px', margin: '0 auto', padding: '2rem 1rem' }}>
      {/* Periyar University Redesigned Header Banner */}
      <div className="periyar-header" style={{ marginBottom: '2rem' }}>
        <div className="header-logo-container">
          <img src="/periyar_logo.png" alt="Periyar University Logo" className="periyar-logo" />
        </div>
        <div className="header-text-container">
          <h1 className="header-title-ta">பெரியார் பல்கலைக்கழகம்</h1>
          <p className="header-subtitle-ta">அரசு பல்கலைக்கழகம், சேலம்.</p>
          <h2 className="header-title-en">PERIYAR UNIVERSITY</h2>
          <p className="header-meta-en">
            State University - NAAC 'A++' Grade - NIRF Rank 94 <br />
            State Public University Rank 40 - SDG Institutions Rank Band: 11-50 <br />
            Salem - 636 011, Tamil Nadu, India.
          </p>
        </div>
        <div className="header-sketch-container">
          <img src="/periyar_sketch.png" alt="Thanthai Periyar Sketch" className="periyar-sketch" />
        </div>
      </div>

      <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
        <h2 style={{ color: 'var(--primary-color)', fontSize: '2rem', fontWeight: '700', marginBottom: '0.5rem' }}>
          System Developers
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', maxWidth: '600px', margin: '0 auto' }}>
          Meet the engineering team behind Periyar University's PhD Entrance Examination Portal.
        </p>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '2rem',
        marginBottom: '3rem'
      }}>
        {developers.map((dev, idx) => (
          <div
            key={idx}
            className="card"
            style={{
              position: 'relative',
              overflow: 'hidden',
              borderTop: '5px solid var(--primary-color)',
              boxShadow: 'var(--shadow-md)',
              transition: 'var(--transition-all)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '2rem 1.5rem',
              borderRadius: '0.75rem',
              backgroundColor: 'var(--card-background)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-5px)';
              e.currentTarget.style.boxShadow = 'var(--shadow-lg)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = 'var(--shadow-md)';
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%', justifyContent: 'space-between' }}>
              {/* Card Body: Left Image & Right Details */}
              <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'stretch' }}>
                {/* Left Column: Profile Image */}
                <div style={{ flexShrink: 0, width: '100px' }}>
                  <img
                    src={dev.image}
                    alt={dev.name}
                    style={{
                      width: '120px',
                      height: '160px',
                      borderRadius: '0.5rem',
                      objectFit: 'cover',
                      border: '1px solid var(--border-color)',
                      boxShadow: 'var(--shadow-sm)'
                    }}
                  />
                </div>

                {/* Right Column: Text Details & Skills */}
                <div style={{ flexGrow: 1, marginLeft: '1rem' }}>
                  <h3 style={{ margin: 0, color: 'var(--secondary-color)', fontSize: '1.4rem', fontWeight: '700', lineHeight: 1.2 }}>
                    {dev.name}
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', marginTop: '0.35rem', marginBottom: '0.75rem' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <span className="user-badge" style={{ backgroundColor: 'var(--primary-light)', color: 'var(--primary-color)', fontSize: '0.75rem', padding: '0.15rem 0.5rem' }}>
                        {dev.degree}
                      </span>
                      <span className="user-badge" style={{ backgroundColor: 'var(--success-bg)', color: 'var(--success-color)', fontSize: '0.75rem', padding: '0.15rem 0.5rem', fontWeight: '600' }}>
                        {dev.role}
                      </span>
                    </div>
                  </div>

                  {/* Skills Section inside Right Column */}
                  <div>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      color: 'var(--text-secondary)',
                      fontSize: '0.8rem',
                      fontWeight: '700',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      marginBottom: '0.5rem'
                    }}>
                      <Code size={14} />
                      <span>Skills & Technologies</span>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                      {dev.skills.map((skill, sIdx) => (
                        <span
                          key={sIdx}
                          style={{
                            fontSize: '0.75rem',
                            padding: '0.2rem 0.5rem',
                            backgroundColor: '#f1f5f9',
                            color: '#334155',
                            borderRadius: '0.25rem',
                            fontWeight: '600',
                            border: '1px solid #e2e8f0'
                          }}
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Separator line */}
              <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '1.25rem 0' }} />

              {/* Contact Details Section */}
              <div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  color: 'var(--text-secondary)',
                  fontSize: '0.8rem',
                  fontWeight: '700',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: '0.75rem'
                }}>
                  <Cpu size={14} />
                  <span>Contact Details</span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.9rem' }}>
                  <a
                    href={dev.portfolio}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      color: 'var(--primary-color)',
                      textDecoration: 'none',
                      fontWeight: '500',
                      transition: 'var(--transition-all)'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.color = 'var(--primary-hover)'}
                    onMouseLeave={(e) => e.currentTarget.style.color = 'var(--primary-color)'}
                  >
                    <span style={{ fontSize: '1.1rem' }}>🌐</span>
                    <span style={{ textDecoration: 'underline' }}>{dev.portfolio}</span>
                  </a>

                  <a
                    href={`mailto:${dev.email}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      color: 'var(--text-primary)',
                      textDecoration: 'none',
                      fontWeight: '500',
                      transition: 'var(--transition-all)'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.color = 'var(--primary-color)'}
                    onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
                  >
                    <span style={{ fontSize: '1.1rem' }}>✉</span>
                    <span> &nbsp;  {dev.email}</span>
                  </a>

                  <a
                    href={`tel:${dev.phone.replace(/\s+/g, '')}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      color: 'var(--text-primary)',
                      textDecoration: 'none',
                      fontWeight: '500',
                      transition: 'var(--transition-all)'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.color = 'var(--primary-color)'}
                    onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
                  >
                    <span style={{ fontSize: '1.1rem' }}>📞</span>
                    <span>{dev.phone}</span>
                  </a>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', marginTop: '2rem' }}>
        <button
          className="btn btn-secondary"
          onClick={() => navigate(-1)}
          style={{ padding: '0.5rem 2rem' }}
        >
          Go Back
        </button>
        <button
          className="btn btn-primary"
          onClick={() => navigate('/')}
          style={{ padding: '0.5rem 2rem' }}
        >
          Portal Home
        </button>
      </div>
    </div>
  );
}
