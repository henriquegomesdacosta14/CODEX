CREATE TABLE journeys (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(160) NOT NULL,
  slug VARCHAR(180) NOT NULL UNIQUE,
  audience VARCHAR(80) NOT NULL,
  description TEXT NOT NULL,
  total_days INT NOT NULL,
  daily_unlock_default TINYINT(1) NOT NULL DEFAULT 1,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE journey_days (
  id INT AUTO_INCREMENT PRIMARY KEY,
  journey_id INT NOT NULL,
  day_number INT NOT NULL,
  theme VARCHAR(180) NOT NULL,
  bible_reference VARCHAR(120) NOT NULL,
  bible_text TEXT NOT NULL,
  devotional LONGTEXT NOT NULL,
  renunciation TEXT NOT NULL,
  practical_action TEXT NOT NULL,
  final_prayer TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY unique_journey_day (journey_id, day_number),
  FOREIGN KEY (journey_id) REFERENCES journeys(id) ON DELETE CASCADE
);

CREATE TABLE access_groups (
  id INT AUTO_INCREMENT PRIMARY KEY,
  journey_id INT NOT NULL,
  access_code VARCHAR(24) NOT NULL UNIQUE,
  group_name VARCHAR(160) NOT NULL,
  group_type ENUM('casal', 'individual', 'grupo', 'igreja', 'terapeuta') NOT NULL DEFAULT 'casal',
  facilitator_name VARCHAR(160) NULL,
  start_date DATE NOT NULL,
  daily_unlock_enabled TINYINT(1) NOT NULL DEFAULT 1,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (journey_id) REFERENCES journeys(id)
);

CREATE TABLE group_members (
  id INT AUTO_INCREMENT PRIMARY KEY,
  access_group_id INT NOT NULL,
  member_label VARCHAR(80) NOT NULL,
  member_name VARCHAR(160) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (access_group_id) REFERENCES access_groups(id) ON DELETE CASCADE
);

CREATE TABLE day_progress (
  id INT AUTO_INCREMENT PRIMARY KEY,
  access_group_id INT NOT NULL,
  day_number INT NOT NULL,
  completed TINYINT(1) NOT NULL DEFAULT 0,
  completed_at DATETIME NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY unique_group_progress_day (access_group_id, day_number),
  FOREIGN KEY (access_group_id) REFERENCES access_groups(id) ON DELETE CASCADE
);

CREATE TABLE day_notes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  access_group_id INT NOT NULL,
  member_id INT NOT NULL,
  day_number INT NOT NULL,
  note LONGTEXT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY unique_member_note_day (access_group_id, member_id, day_number),
  FOREIGN KEY (access_group_id) REFERENCES access_groups(id) ON DELETE CASCADE,
  FOREIGN KEY (member_id) REFERENCES group_members(id) ON DELETE CASCADE
);

INSERT INTO journeys (
  title,
  slug,
  audience,
  description,
  total_days,
  daily_unlock_default
) VALUES (
  '21 Dias de Devocional para Casal e Família',
  '21-dias-casal-familia',
  'casais',
  'Um propósito de restauração, unidade e presença de Deus no lar.',
  21,
  1
);
