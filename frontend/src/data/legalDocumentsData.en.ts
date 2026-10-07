import type { LegalDocument } from './legalDocumentsData'

/**
 * Flama Platform Legal Documents Data Engine (English Edition)
 * Standardized schema and official English legal texts for all core platform policies.
 * 
 * Documents:
 * 1. terms: Terms of Service & Platform Protection Agreement
 * 2. privacy: Data Privacy & Protection Policy (Compliant with Decree 13/2023/ND-CP)
 * 3. marketplace-guidelines: Marketplace Operating Regulations & Intellectual Property Guidelines
 * 4. community-guidelines: Community Standards & Code of Conduct
 * 5. cookies: Cookie & Local Storage Policy
 */
export const legalDocumentsEn: Record<string, LegalDocument> = {
  terms: {
    id: 'terms',
    title: 'Terms of Service & Platform Protection Agreement',
    officialBadge: 'Official Platform Legal Standard v2.0',
    lastUpdated: '13/09/2026',
    effectiveDate: '15/09/2026',
    version: 'v2.0',
    readTimeMinutes: 18,
    executiveSummary:
      'This document establishes a legally binding service agreement between users and the Flama Learning Platform. The regulations set forth account eligibility, payment processing mechanisms via the payOS gateway, disclaimer provisions for satellite services (Flama Connect and Flama Audio), enforcement sanctions, and statutory limitations of liability.',
    clauses: [
      {
        id: 'clause-terms-scope',
        clauseNumber: 'Article 1',
        title: 'Scope of Application & Acceptance of Terms',
        summary: 'Establishes the legal validity of these Terms of Service and prerequisites for platform participation.',
        content: [
          'Welcome to Flama (hereinafter referred to as the "Platform", "System", or "We"). By accessing, creating an account, installing workstation companion software, or utilizing any feature on Flama, you acknowledge that you have carefully read, understood, and agreed to be unconditionally bound by these Terms of Service and all publicly published policies.',
        ],
        subClauses: [
          {
            id: 'terms-1-1',
            clauseNumber: '1.1',
            title: 'Entire Legal Agreement Framework',
            content: [
              'These Terms of Service, together with the Privacy Policy, Marketplace Operating Regulations & Intellectual Property Guidelines, and Community Standards, constitute the entire and integrated legal agreement between you and Flama regarding service usage.',
              'In the event of any discrepancy between interface summaries and the detailed provisions of this official legal instrument, the detailed text of this official document shall govern and prevail.',
            ],
          },
          {
            id: 'terms-1-2',
            clauseNumber: '1.2',
            title: 'Legal Capacity & Age Requirements',
            content: [
              'Flama services are intended for individuals aged fifteen (15) years or older possessing full civil act capacity in accordance with the Civil Code of Vietnam.',
              'Where a learner is under fifteen (15) years of age, account registration and all financial transactions on the platform must be conducted with the explicit consent, guarantee, and direct supervision of a parent or legal guardian.',
            ],
          },
          {
            id: 'terms-1-3',
            clauseNumber: '1.3',
            title: 'Effectiveness & Amendments to Regulations',
            content: [
              'Flama reserves the right to update, amend, or adjust the provisions of these terms at any time to satisfy technical operating requirements or comply with changes in applicable law.',
              'Material changes shall be notified at least seven (07) days in advance via platform notification banners or registered user email prior to formally taking legal effect.',
            ],
          },
        ],
      },
      {
        id: 'clause-terms-account',
        clauseNumber: 'Article 2',
        title: 'User Accounts & Secure Session Management',
        summary: 'Governs identity verification obligations, password security, and automated defense against brute-force attacks.',
        content: [
          'To access full learning features, persist Spaced Repetition learning progress, and participate in the Marketplace, users must establish a unique account on the Flama system.',
        ],
        subClauses: [
          {
            id: 'terms-2-1',
            clauseNumber: '2.1',
            title: 'Registration & Identity Data Accuracy',
            content: [
              'Users covenant to furnish a valid, accessible email address and truthful profile information at the time of registration.',
              'Impersonation of any individual or entity, creation of fraudulent accounts, or automated batch registrations (bot registration) are strictly prohibited.',
            ],
          },
          {
            id: 'terms-2-2',
            clauseNumber: '2.2',
            title: 'Security Obligations & Rate-Limited Anti-Brute-Force Lockout',
            content: [
              'Users maintain sole responsibility for safeguarding access credentials and authentication devices. Flama applies robust one-way cryptographic hashing standards where plaintext passwords cannot be recovered.',
              'To protect the system against credential stuffing and brute-force intrusion attempts, our authentication security service automatically activates an exponential rate-limited lockout mechanism for IP addresses or accounts exceeding safety thresholds of failed authentication attempts.',
            ],
          },
          {
            id: 'terms-2-3',
            clauseNumber: '2.3',
            title: 'Non-Transferability of Accounts',
            content: [
              'Each Flama account represents the exclusive personal identifier asset of the registered holder. You may not sell, assign, lease, share login credentials, or delegate third parties to operate your account under any circumstances.',
              'All activities originating from an account are conclusively deemed by the system to be sovereign actions executed with the full consent of the account owner.',
            ],
          },
        ],
        callout: {
          type: 'statutory',
          label: 'Session Security Statutory Notice',
          text: 'Users are legally obligated to promptly notify Flama technical support upon detecting any indication of unauthorized access or security vulnerabilities associated with their personal account.',
        },
      },
      {
        id: 'clause-terms-payos',
        clauseNumber: 'Article 3',
        title: 'payOS Payment Integration & Financial Transaction Rules',
        summary: 'Governs VietQR transactions via the payOS gateway, order validity windows, non-refundable digital content, and creator escrow balances.',
        content: [
          'Flama operates a digital payment infrastructure supporting the purchase of learning materials, flashcard collections, specialized note formatting templates, and platform community support contributions. All online transactions are routed through the independent intermediary payment gateway payOS.',
        ],
        subClauses: [
          {
            id: 'terms-3-1',
            clauseNumber: '3.1',
            title: 'Independent Payment Processor payOS',
            content: [
              'The payOS payment gateway (operated by PAYOS Technology JSC under an intermediary payment license and compliant with the State Bank of Vietnam VietQR network standard) is the independent entity responsible for routing and technically processing banking transactions.',
              'All prices listed on Flama are denominated and payable in Vietnam Dong (VND). When scanning VietQR codes or initiating bank transfers, users are responsible for verifying the exact payment amount and transfer narrative matching order specifications.',
            ],
          },
          {
            id: 'terms-3-2',
            clauseNumber: '3.2',
            title: 'Payment Session Expiration & Overdue Handling (30-Minute Window)',
            content: [
              'Each payment checkout link and order QR code maintains an exact validity duration of thirty (30) minutes (1800 seconds) from the moment of initialization.',
              'Funds transferred after the payment link has expired, or transferred with an erroneous payment reference code, cannot be automatically reconciled for instant fulfillment. Such transactions will transition to a pending review state requiring manual reconciliation.',
            ],
          },
          {
            id: 'terms-3-3',
            clauseNumber: '3.3',
            title: 'Digital Content Nature & Waiver of Right of Withdrawal',
            content: [
              'Products on the Flama Marketplace (study card collections, note templates) constitute digital educational content delivered and made immediately accessible to the user account upon verified banking confirmation.',
              'Pursuant to electronic commerce laws and consumer protection regulations governing immediate-consumption digital goods, by confirming payment, the user consents to immediate fulfillment and waives any right of cancellation, withdrawal, or discretionary refund absent verified technical default.',
            ],
          },
          {
            id: 'terms-3-4',
            clauseNumber: '3.4',
            title: 'Refund Exceptions Policy',
            content: [
              'Flama only considers refunds in the following specifically verified technical force majeure circumstances:',
              '1. Duplicate Billing: The user is debited more than once for the identical order transaction within a 24-hour period.',
              '2. Permanent Grant Failure: The transaction is successfully confirmed by payOS, but Flama fails to grant access to the educational materials and technical support cannot resolve the issue within seven (07) business days of written notice.',
              'Because VietQR and payOS do not support automated reverse payment refunds, approved refunds will be executed manually via domestic bank wire transfer within fourteen (14) business days. Refund claims must be submitted through official Support channels within seven (07) days of the transaction date.',
            ],
          },
          {
            id: 'terms-3-5',
            clauseNumber: '3.5',
            title: 'Creator Revenue Wallet & Interim Escrow Balance',
            content: [
              'When a Creator’s paid learning material is successfully purchased, the net proceeds (following deduction of tiered platform fees: 10% standard, 5% for verified creators) are credited to the creator’s internal platform balance.',
              'Payout functionality is currently scheduled on our roadmap pending finalization of tax reconciliation and identity verification infrastructure. All accumulated revenue is securely held by Flama as an internal escrow balance until the official launch of tax-compliant payout services.',
            ],
          },
        ],
        callout: {
          type: 'warning',
          label: 'Prohibition of Financial Fraud & Illegal Chargebacks',
          text: 'Any use of unauthorized bank accounts, payment fraud, or bad-faith chargeback disputes following successful download of learning materials shall result in immediate permanent account termination, forfeiture of access, and formal referral to law enforcement agencies.',
        },
      },
      {
        id: 'clause-terms-connect',
        clauseNumber: 'Article 4',
        title: 'Flama Connect Companion Service & Study Material Disclaimer',
        summary: 'Governs local protocol loopback architecture, workstation privacy protection, and user copyright responsibility for mined data.',
        content: [
          'Flama provides the Flama Connect companion service operating as a local workstation protocol bridge designed to interface seamlessly with browser companion extensions for one-click vocabulary and terminology mining.',
        ],
        subClauses: [
          {
            id: 'terms-4-1',
            clauseNumber: '4.1',
            title: 'Local Loopback Interface Isolation',
            content: [
              'Flama Connect is engineered to operate exclusively on a closed internal loopback network on the user’s workstation and does not listen on public network interfaces. Users maintain complete responsibility for firewall configuration and securing their operating environment against unauthorized local workstation queries.',
            ],
          },
          {
            id: 'terms-4-2',
            clauseNumber: '4.2',
            title: 'Security of Flama Connect Authentication Token',
            content: [
              'The Flama Connect authentication token conveys privileged capabilities (such as card creation and deck catalog inspection). Users must safeguard this credential within their browser extension and immediately revoke it via account settings upon any suspected compromise.',
            ],
          },
          {
            id: 'terms-4-3',
            clauseNumber: '4.3',
            title: 'Fair Use & Private Study Principle',
            content: [
              'Users employ Flama Connect to extract illustrative sentences, terminology, concept definitions, multimedia, and audio from external educational and media sources.',
              'Flama acts solely as an intermediary technical transport bridge. Users warrant and represent that all mined content is utilized strictly for non-commercial personal research and private study in compliance with fair use principles under applicable intellectual property laws.',
            ],
          },
          {
            id: 'terms-4-4',
            clauseNumber: '4.4',
            title: 'Strict Prohibition on Redistribution & Commercialization',
            content: [
              'Users are strictly forbidden from packaging, publicly sharing, or offering for commercial sale on Flama Marketplace any card collections containing copyrighted commercial dictionary databases or third-party proprietary materials without prior written consent.',
            ],
          },
          {
            id: 'terms-4-5',
            clauseNumber: '4.5',
            title: 'Third-Party Extension Compatibility Disclaimer',
            content: [
              'The Flama Connect service is provided strictly on an "AS-IS" basis. Flama does not warrant uninterrupted compatibility whenever third-party browser extensions or browser platform manifest specifications alter connection methodologies or security policies without notice.',
            ],
          },
        ],
      },
      {
        id: 'clause-terms-audio',
        clauseNumber: 'Article 5',
        title: 'Flama Audio Companion Service & AI Voice Licensing',
        summary: 'Governs Flama Audio desktop application usage, third-party API expense disclaimers, and neural voice synthesis licensing standards.',
        content: [
          'Flama Audio is an independent desktop companion application designed for learners to synthesize natural multilingual audio pronunciation utilizing advanced local neural speech engines and cloud providers.',
        ],
        subClauses: [
          {
            id: 'terms-5-1',
            clauseNumber: '5.1',
            title: 'Third-Party API Keys & Incurred Billing Responsibility',
            content: [
              'When users configure third-party provider API keys (such as OpenAI, Microsoft Azure, Google Cloud) within Flama, these credentials are encrypted at rest using industry-standard symmetric ciphers.',
              'Flama maintains zero visibility or authority over third-party billing. Users bear 100% responsibility for all incurred provider charges, usage quotas, and payment policies associated with their chosen external cloud speech services.',
            ],
          },
          {
            id: 'terms-5-2',
            clauseNumber: '5.2',
            title: 'Phonetic Accuracy & Neural Speech Synthesis Disclaimers',
            content: [
              'Audio generated by deep neural models is synthesized automatically. Flama makes no warranties regarding absolute phonetic perfection, technical intonation accuracy, or pedagogical suitability of generated audio clips.',
              'Learners must independently verify pronunciation when preparing for rigorous academic or professional certification examinations.',
            ],
          },
          {
            id: 'terms-5-3',
            clauseNumber: '5.3',
            title: 'AI Voice Licensing & Attribution Requirements',
            content: [
              'Synthetic voice models integrated into Flama Audio (including local open-weight engines and commercial cloud services) are governed by their respective open-source licenses or terms of service.',
              'Users distributing public study materials incorporating synthetic audio must comply with mandatory attribution guidelines as specified by model licensors, and are strictly prohibited from utilizing synthetic voices for defamatory, deceptive, deepfake, or unlawful commercial purposes.',
            ],
          },
          {
            id: 'terms-5-4',
            clauseNumber: '5.4',
            title: 'Client-Side Workstation Environment Disclaimer',
            content: [
              'Flama Audio executes locally within the user’s operating system environment. Flama disclaims liability for audio hardware conflicts, CPU/GPU resource utilization, or interference caused by third-party antivirus software.',
            ],
          },
        ],
      },
      {
        id: 'clause-terms-suspension',
        clauseNumber: 'Article 6',
        title: 'Account Suspension, Sanctions & Service Termination',
        summary: 'Technical account disabling mechanisms, grounds for immediate service termination, and handling of infringing escrow balances.',
        content: [
          'To preserve a trusted and secure learning environment for the community, Flama enforces strict monitoring standards and disciplinary sanctions.',
        ],
        subClauses: [
          {
            id: 'terms-6-1',
            clauseNumber: '6.1',
            title: 'Account Deactivation & Session Severance',
            content: [
              'When an account is deactivated due to violations, the Flama system immediately terminates all active authentication sessions, displays a suspension notification upon login attempts, and invalidates all associated companion service tokens.',
            ],
          },
          {
            id: 'terms-6-2',
            clauseNumber: '6.2',
            title: 'Grounds for Immediate Suspension or Termination',
            content: [
              'Flama reserves full authority to suspend, restrict, or permanently terminate user access without prior notice under the following circumstances:',
              '1. Technical Attacks: Exploiting security vulnerabilities, unauthorized data scraping, injecting malicious HTML/JavaScript into study cards, or launching denial-of-service attempts.',
              '2. Payment Fraud: Utilizing stolen financial credentials, forging transfer narratives, or executing fraudulent chargeback disputes against the payOS gateway.',
              '3. Repeat Copyright Infringement: Repeatedly uploading intellectual property infringing materials pursuant to our Three-Strike Policy.',
              '4. Toxic Conduct: Disseminating hate speech, obscene content, or harassing community members or support personnel.',
            ],
          },
          {
            id: 'terms-6-3',
            clauseNumber: '6.3',
            title: 'Consequences of Termination for Breach',
            content: [
              'Accounts permanently terminated for serious breach immediately forfeit access to all purchased learning materials. Any escrow balances accrued through fraudulent activities or copyright infringement will be frozen and handled in accordance with statutory regulations.',
            ],
          },
        ],
      },
      {
        id: 'clause-terms-liability',
        clauseNumber: 'Article 7',
        title: 'Limitation of Liability & Force Majeure',
        summary: 'Disclaimers of academic warranties, aggregate liability capped at 500,000 VND, and force majeure events.',
        content: [
          'To the maximum extent permitted by Vietnamese law, Flama’s legal liability regarding technical and service contingencies is established as follows:',
        ],
        subClauses: [
          {
            id: 'terms-7-1',
            clauseNumber: '7.1',
            title: 'AS-IS & AS-AVAILABLE Warranty Disclaimer',
            content: [
              'The platform, web interface, learning algorithms, and companion services are provided on an "AS-IS" and "AS-AVAILABLE" basis. Flama makes no implied or express warranties that the service will remain uninterrupted, bug-free, or fully satisfy individual user expectations.',
            ],
          },
          {
            id: 'terms-7-2',
            clauseNumber: '7.2',
            title: 'Disclaimer of Academic Examination Results',
            content: [
              'Flama serves as an assistive tool for retention optimization and review scheduling. Flama makes no guarantee that utilizing the platform will ensure success in certification examinations, professional assessments, or specific academic outcomes.',
            ],
          },
          {
            id: 'terms-7-3',
            clauseNumber: '7.3',
            title: 'Aggregate Liability Cap',
            content: [
              'In all disputes or damages where Flama is established to bear direct fault, Flama’s total aggregate liability toward any individual user shall not exceed the greater of:',
              '(a) The total sum paid by such user to Flama during the three (03) months immediately preceding the date of the claim; or',
              '(b) 500,000 VND (Five Hundred Thousand Vietnam Dong).',
            ],
          },
          {
            id: 'terms-7-4',
            clauseNumber: '7.4',
            title: 'Force Majeure Events',
            content: [
              'Flama is excused from all performance obligations in the event of interruptions resulting from circumstances beyond reasonable control, including undersea internet fiber ruptures, cloud infrastructure outages, national banking network failures, natural disasters, epidemics, or administrative orders issued by competent governmental authorities.',
            ],
          },
        ],
      },
      {
        id: 'clause-terms-governing',
        clauseNumber: 'Article 8',
        title: 'Governing Law & Dispute Resolution Jurisdiction',
        summary: 'Designation of applicable legal jurisdiction and competent court forums in Vietnam.',
        content: [
          'These Terms of Service are construed and governed in all respects by the laws of the Socialist Republic of Vietnam.',
          'Any dispute arising out of or in connection with the use of the platform shall first be submitted to good-faith amicable negotiation between the parties. In the event negotiations fail to achieve resolution within thirty (30) days, the dispute shall be submitted to the competent People’s Court in Vietnam for statutory adjudication.',
        ],
      },
    ],
  },

  privacy: {
    id: 'privacy',
    title: 'Data Privacy & Protection Policy',
    officialBadge: 'Compliant with Decree 13/2023/ND-CP',
    lastUpdated: '13/09/2026',
    effectiveDate: '15/09/2026',
    version: 'v2.0',
    readTimeMinutes: 16,
    executiveSummary:
      'Flama’s Data Privacy Policy strictly adheres to Vietnam’s Personal Data Protection Decree (Decree 13/2023/ND-CP). This policy provides complete transparency regarding collected data categories, discloses Spaced Repetition algorithmic telemetry parameters, enforces strict financial data isolation via payOS, and guarantees all 11 statutory Data Subject Rights including the Right to Erasure.',
    clauses: [
      {
        id: 'clause-privacy-framework',
        clauseNumber: 'Article 1',
        title: 'Legal Framework & Personal Data Processing Principles',
        summary: 'Compliance basis under Decree 13/2023/ND-CP and core learner privacy principles.',
        content: [
          'Flama is committed to protecting the personal data of learners in accordance with the highest standards of Vietnamese law, specifically Decree 13/2023/ND-CP on Personal Data Protection, the Law on Cyberinformation Security, and the Law on Cybersecurity.',
        ],
        subClauses: [
          {
            id: 'privacy-1-1',
            clauseNumber: '1.1',
            title: 'Flama Legal Role',
            content: [
              'Within the provision of learning services, Flama functions as a Personal Data Controller and Processor with respect to account information and study progress data generated by users on the system.',
            ],
          },
          {
            id: 'privacy-1-2',
            clauseNumber: '1.2',
            title: 'Core Data Protection Principles',
            content: [
              '1. Lawfulness and Transparency: Data is collected solely with the explicit consent of learners and with transparent processing objectives.',
              '2. Purpose Limitation: Learning telemetry is processed exclusively to optimize knowledge retention for the learner.',
              '3. Data Minimization: Only information strictly necessary for algorithm operation and digital transactions is collected.',
              '4. Integrity and Confidentiality: State-of-the-art encryption standards are applied to protect against data leakage, unauthorized access, or loss.',
            ],
          },
        ],
      },
      {
        id: 'clause-privacy-taxonomy',
        clauseNumber: 'Article 2',
        title: 'Catalog & Classification of Collected Personal Data',
        summary: 'Delineation across four data tiers: basic identity, study telemetry, payOS payment references, and technical logs.',
        content: [
          'Pursuant to Article 2 of Decree 13/2023/ND-CP, Flama categorizes and collects the following specific classes of personal data:',
        ],
        subClauses: [
          {
            id: 'privacy-2-1',
            clauseNumber: '2.1',
            title: 'Basic Personal Data',
            content: [
              'Includes: Display name, email address, password strings protected with robust industry-standard hashing, profile avatar, personal biography summary, and local timezone configuration (e.g., Asia/Ho_Chi_Minh).',
              'Where learners authenticate via authorized third-party identity providers (such as Google), the system receives and records only the unique provider account identifier and authorized email address.',
            ],
          },
          {
            id: 'privacy-2-2',
            clauseNumber: '2.2',
            title: 'Learning Telemetry & Retention Progress',
            content: [
              'Includes: Personal deck collections, flashcards, study content fields and conceptual knowledge items, review counts, and timestamps recording completion of study sessions.',
            ],
          },
          {
            id: 'privacy-2-3',
            clauseNumber: '2.3',
            title: 'Financial Transaction Data (Strict Isolation via payOS)',
            content: [
              'Flama ABSOLUTELY DOES NOT collect, process, or store bank account numbers, credit or debit card numbers, expiration dates, or CVV/CVC security codes.',
              'The Flama platform stores solely non-identifying transaction receipts provided by payOS for content entitlement activation and statutory tax reconciliation: Order ID, payment reference code, transaction amount in VND, timestamp, and entitlement status.',
            ],
          },
          {
            id: 'privacy-2-4',
            clauseNumber: '2.4',
            title: 'Technical & System Access Data',
            content: [
              'Includes Internet Protocol (IP) addresses, browser User-Agent strings, security authentication logs, session tokens, and interface configuration preferences.',
            ],
          },
        ],
        callout: {
          type: 'info',
          label: 'Payment Infrastructure Isolation Commitment',
          text: 'All banking details entry and QR scanning transpire entirely within the isolated secure infrastructure of payOS and the user’s banking application. Flama never touches sensitive payment card information.',
        },
      },
      {
        id: 'clause-privacy-srs',
        clauseNumber: 'Article 3',
        title: 'Spaced Repetition Algorithmic Telemetry Transparency',
        summary: 'Discloses the Ebbinghaus Forgetting Curve foundation and the cognitive telemetry captured during review sessions.',
        content: [
          'Our Spaced Repetition engine operates on the scientific foundation of the Ebbinghaus Forgetting Curve to determine the optimal moment for reviewing a knowledge unit prior to cognitive decay. All recorded telemetry serves solely to schedule cards for your personal study sessions.',
        ],
        subClauses: [
          {
            id: 'privacy-3-1',
            clauseNumber: '3.1',
            title: 'Strict Purpose Limitation',
            content: [
              'Card review interaction data is utilized exclusively to calculate subsequent repetition intervals. This telemetry is never sold to third parties, never utilized for commercial profiling, and never used for targeted behavioral advertising.',
            ],
          },
          {
            id: 'privacy-3-2',
            clauseNumber: '3.2',
            title: 'Telemetry Captured During Each Review',
            content: [
              'During each study card interaction, the system records standardized parameters to personalize retention trajectories:',
              '1. Cognitive Response Latency: Interaction timestamps and cognitive response intervals measured from card presentation until grade selection.',
              '2. Recall History: Subjective recall evaluation ratings (review grades indicating recall difficulty) and card distribution phases in the learning cycle.',
              '3. Learning Progression: Intraday short-term learning steps, cumulative successful repetitions, and count of required reinforcement events.',
              '4. Adaptive Interval Calculation: Mathematical parameters estimating memory durability, cognitive difficulty, and next due dates normalized to the user’s timezone.',
            ],
          },
          {
            id: 'privacy-3-3',
            clauseNumber: '3.3',
            title: 'Automatic Suspension of Cards Requiring Reinforcement',
            content: [
              'When a study card exceeds the maximum threshold of failed recall attempts, the algorithm automatically flags the item for reinforcement and temporarily suspends it from automated queues. This mechanism shields learners from negative cognitive fatigue cycles and allows thoughtful review of study methodology.',
            ],
          },
        ],
      },
      {
        id: 'clause-privacy-rights',
        clauseNumber: 'Article 4',
        title: 'Data Subject Rights under Article 9 of Decree 13/2023/ND-CP',
        summary: 'Comprehensive realization of all 11 statutory rights for Flama users.',
        content: [
          'Flama respects and provides complete technical capabilities and administrative channels for learners to exercise all eleven (11) statutory rights under Article 9 of Decree 13/2023/ND-CP:',
          '1. Right to be informed: Clear disclosure of all data processing operations through this Policy.',
          '2. Right to consent: Freedom to grant or decline consent for optional data upon registration.',
          '3. Right of access: Review full profile information and study progress on Dashboard and Profile views.',
          '4. Right to withdraw consent: Revoke previously granted consent by deactivating account or contacting support.',
          '5. Right to erasure (Right to be Forgotten): Request permanent destruction of personal and learning data.',
          '6. Right to restrict processing: Request temporary suspension of data processing via account lockdown features.',
          '7. Right to data portability: Export personal decks in standard open formats (.apkg, CSV) and generate printable study worksheets.',
          '8. Right to object to processing: Object to the utilization of data for non-mandatory academic statistical studies.',
          '9. Right to lodge complaints and reports: Submit complaints directly to Flama’s Data Protection Officer or statutory authorities.',
          '10. Right to claim damages: Seek legal remedies when unlawful data violations cause actual substantiated damages.',
          '11. Right to self-protection: Utilize tools for password updating, remote session termination, and companion API token revocation.',
        ],
      },
      {
        id: 'clause-privacy-erasure',
        clauseNumber: 'Article 5',
        title: 'Tiered Data Deletion & Statutory Accounting Exceptions',
        summary: 'Workflows for purge of learning telemetry alongside statutory accounting archiving obligations.',
        content: [
          'When a user exercises the right to permanent data erasure or terminates their account, Flama initiates a technical deletion workflow operating across two distinct processing pipelines:',
        ],
        subClauses: [
          {
            id: 'privacy-5-1',
            clauseNumber: '5.1',
            title: 'Automated Cascading Data Destruction Workflow',
            content: [
              'The system executes a thorough cascading purge to immediately and irreversibly destroy: User profile data, third-party authentication links, study records, detailed review histories, card progress data, scheduling algorithm parameters, and active authentication sessions.',
            ],
          },
          {
            id: 'privacy-5-2',
            clauseNumber: '5.2',
            title: 'Statutory Accounting & Tax Retention Exception',
            content: [
              'Pursuant to Articles 16 and 17 of Decree 13/2023/ND-CP, the Accounting Law, and the Tax Administration Law of Vietnam, financial records documenting monetary transactions may not be deleted immediately and must be archived for statutory audit obligations.',
              'To ensure privacy, Flama applies complete irreversible anonymization: All identifying personal associations with financial transaction records are permanently severed. The individual identity of the user is severed from payment logs, preserving solely non-identifying accounting vouchers for statutory tax audit purposes.',
            ],
          },
        ],
        callout: {
          type: 'statutory',
          label: 'Statutory Archiving Exception Notice',
          text: 'Preservation of anonymized financial vouchers is a mandatory statutory obligation under Vietnamese Accounting Law and does not constitute a violation of personal data erasure rights.',
        },
      },
      {
        id: 'clause-privacy-breach',
        clauseNumber: 'Article 6',
        title: 'Personal Data Breach Notification SLA',
        summary: 'Compliance commitment with 72-hour notification SLA to regulatory agency A05 and DPO contact information.',
        content: [
          'In the event of a cybersecurity incident resulting in the risk of leakage, loss, or unauthorized access to personal data of learners, Flama commits to:',
          '1. Regulatory Authority Notification: Submit a formal written report to the Department of Cybersecurity and High-Tech Crime Prevention (A05 - Ministry of Public Security) within seventy-two (72) hours of discovering the incident, pursuant to Article 23 of Decree 13/2023/ND-CP.',
          '2. User Incident Advisory: Immediately alert affected users via email and in-app system notifications, including recommendations to mitigate risk (such as updating passwords and revoking companion tokens).',
        ],
        subClauses: [
          {
            id: 'privacy-6-1',
            clauseNumber: '6.1',
            title: 'Data Protection Officer (DPO) Contact Channel',
            content: [
              'For all inquiries, complaints, or enforcement requests regarding personal data protection, please contact: Flama Data Protection Officer via email at privacy@flama.vn or submit a request via our User Support channel (/support).',
            ],
          },
        ],
      },
    ],
  },

  'marketplace-guidelines': {
    id: 'marketplace-guidelines',
    title: 'Marketplace Operating Regulations & Intellectual Property Guidelines',
    officialBadge: 'Copyright Framework & Clone Overlay v2.0',
    lastUpdated: '13/09/2026',
    effectiveDate: '15/09/2026',
    version: 'v2.0',
    readTimeMinutes: 15,
    executiveSummary:
      'These regulations demarcate intellectual property boundaries among the Flama Platform, Deck Creators, and Learners. This document formalizes the legal protective shields provided by the Clone Overlay architecture and establishes a standard Notice & Takedown procedure.',
    clauses: [
      {
        id: 'clause-market-division',
        clauseNumber: 'Article 1',
        title: 'Three-Way Intellectual Property Division',
        summary: 'Establishes clear intellectual property rights among Platform, Creators, and Learners.',
        content: [
          'The educational material sharing model on Flama establishes a transparent three-way intellectual property structure to guarantee the legitimate rights of all participating parties:',
        ],
        subClauses: [
          {
            id: 'market-1-1',
            clauseNumber: '1.1',
            title: 'Platform Intellectual Property (Platform IP)',
            content: [
              'Flama exclusively owns all software source code, user interface designs (UI/UX), database architectures, Spaced Repetition algorithms, Clone Overlay technical infrastructure, the "Flama" trademark, brand marks, and the domain flama.vn.',
              'No user or creator may copy, reverse engineer, scrape data, or utilize Flama trademarks for independent commercial endeavors without prior written authorization.',
            ],
          },
          {
            id: 'market-1-2',
            clauseNumber: '1.2',
            title: 'Deck Creators Intellectual Property (Deck Creators IP)',
            content: [
              'Creators retain full copyright and intellectual property rights over their original compiled content, including: Grammar explanations, original illustrative examples, proprietary mnemonic techniques, curriculum structures, and original voice recordings recorded by the creator.',
              'By publishing a study deck to the Flama Marketplace (whether free or paid), the Creator grants Flama a non-exclusive, worldwide, royalty-free license (independent of agreed marketplace revenue shares) to host, index for search, display, stream audio, and distribute access rights to learners who install the deck.',
            ],
          },
          {
            id: 'market-1-3',
            clauseNumber: '1.3',
            title: 'Learners Intellectual Property (Learners IP)',
            content: [
              'Learners own all personal annotations, custom field overlay layers, supplemental cards added independently, and their entire personal SRS review history and progress telemetry.',
              'A learner’s personal notes remain strictly confidential within their private installation and are never automatically transferred to original creators or third parties unless the learner explicitly submits a Deck Change Request.',
            ],
          },
        ],
      },
      {
        id: 'clause-market-overlay',
        clauseNumber: 'Article 2',
        title: 'Legal Mechanism & Protective Shields of the Clone Overlay Architecture',
        summary: 'Logical Overlay Architecture establishing twin shields: creator anti-theft protection and learner study investment preservation.',
        content: [
          'Unlike legacy flashcard platforms that clone duplicate data stores risking copyright leakage, Flama deploys an innovative Logical Overlay Architecture that strictly decouples creator source materials from private learner study spaces.',
        ],
        subClauses: [
          {
            id: 'market-2-1',
            clauseNumber: '2.1',
            title: 'Nature of Logical Overlay Installation',
            content: [
              'When a learner installs a deck from the Marketplace, the system does not generate duplicate database copies of original note contents. The learner’s installation links directly to the creator’s official release.',
              'All learner modifications persist exclusively as an isolated personalized overlay layer within the learner’s account, leaving the creator’s underlying master record completely unmutated.',
            ],
          },
          {
            id: 'market-2-2',
            clauseNumber: '2.2',
            title: 'Anti-Theft Shield for Creators',
            content: [
              'Because learners do not possess an independent database copy of the deck, learners cannot re-export or re-list the creator’s deck as a new standalone product on the Flama Marketplace.',
              'This technical architecture eliminates pirated cloning and vigorously protects the pedagogical investment of genuine creators.',
            ],
          },
          {
            id: 'market-2-3',
            clauseNumber: '2.3',
            title: 'Study Investment Shield for Learners',
            content: [
              'Learners invest substantial time accumulating memory retention telemetry. This progress data and review history remain securely anchored to the learner’s personal account.',
              'Even if a creator unpublishes, archives, or deletes a deck from the public Marketplace, existing installed overlay decks remain perpetually active within the learner’s private study space. A learner’s study investment is never extinguished.',
            ],
          },
          {
            id: 'market-2-4',
            clauseNumber: '2.4',
            title: 'Deck Change Request Mechanism',
            content: [
              'Learners may suggest typographical corrections or semantic improvements to creators via the Deck Change Request feature.',
              'By submitting such suggestions, the learner grants the creator a non-exclusive, perpetual license to incorporate the suggested revisions into future public deck updates.',
            ],
          },
        ],
      },
      {
        id: 'clause-market-standards',
        clauseNumber: 'Article 3',
        title: 'Copyright Standards & Prohibited Content Catalog',
        summary: 'Strict prohibition on scanned commercial textbooks, unreleased exam papers, and commercial dictionary databases.',
        content: [
          'All learning materials listed on the Marketplace must represent the legitimate creative intellectual product of the creator or incorporate openly licensed educational resources.',
          'The following activities are strictly prohibited on the Flama Marketplace:',
          '1. Scanning or verbatim copying of copyrighted commercial textbooks or educational curricula across any discipline without explicit written publisher authorization.',
          '2. Distributing official test questions from standardized examinations or professional credentialing assessments prior to authorized public release.',
          '3. Unauthorized extraction of entire databases belonging to commercial proprietary dictionaries.',
          '4. Uploading audio files, music tracks, or graphical images infringing third-party copyrights.',
        ],
        callout: {
          type: 'warning',
          label: 'Zero-Tolerance Policy for Pirated Educational Content',
          text: 'Flama proactively audits and immediately removes any study deck that unlawfully reproduces commercial textbooks or violates publishing copyrights.',
        },
      },
      {
        id: 'clause-market-takedown',
        clauseNumber: 'Article 4',
        title: 'Copyright Intake & Takedown Procedure (Notice & Takedown)',
        summary: '24-48 hour response SLA, material isolation, 10-day counter-notice window, and 14-day court filing deadline.',
        content: [
          'Flama respects the intellectual property rights of all rights holders and operates an official Notice & Takedown process compliant with the Intellectual Property Law of Vietnam and international conventions:',
        ],
        subClauses: [
          {
            id: 'market-4-1',
            clauseNumber: '4.1',
            title: 'Valid Copyright Infringement Notice',
            content: [
              'Copyright owners or their authorized agents must transmit a formal notice to legal@flama.vn or via our Support channel (/support), containing:',
              '(a) A physical or electronic signature of the copyright holder or authorized representative;',
              '(b) Identification of the copyrighted work claimed to have been infringed with proof of ownership;',
              '(c) The specific URL or identifier of the infringing study deck on Flama;',
              '(d) Complete contact details (full name, email, phone number, address);',
              '(e) A formal statement under penalty of perjury affirming that the notice information is accurate and submitted in good faith.',
            ],
          },
          {
            id: 'market-4-2',
            clauseNumber: '4.2',
            title: 'Verification SLA & Emergency Quarantine (24–48h SLA)',
            content: [
              'Within twenty-four to forty-eight (24–48) business hours of receiving a valid complaint, Flama’s legal team conducts preliminary technical review.',
              'Upon substantiated grounds, Flama immediately executes emergency quarantine: transitioning the deck to private or quarantined status, removing it from Marketplace search indexes, and forwarding the notice to the reported creator.',
            ],
          },
          {
            id: 'market-4-3',
            clauseNumber: '4.3',
            title: 'Creator Counter-Notice Procedure (10-Day Window)',
            content: [
              'The creator has ten (10) business days from receipt of quarantine notification to submit a Counter-Notice establishing legitimate rights to the content.',
              'If the creator fails to respond or acknowledges infringement, the deck is permanently removed from the system.',
            ],
          },
          {
            id: 'market-4-4',
            clauseNumber: '4.4',
            title: 'Court Action Window & Restoration (14-Day Window)',
            content: [
              'Upon receipt of a valid Counter-Notice, Flama transmits a copy to the complainant. The complainant has fourteen (14) business days to provide evidence of formal court action filed with a competent court.',
              'If the complainant fails to produce proof of legal proceedings within 14 business days, Flama may restore the deck to normal Marketplace availability.',
            ],
          },
        ],
      },
      {
        id: 'clause-market-strikes',
        clauseNumber: 'Article 5',
        title: 'Three-Strike Repeat Infringer Policy',
        summary: 'Progressive disciplinary scale: Formal warning -> 30-day publishing suspension -> Permanent revocation and forfeiture of revenue.',
        content: [
          'To deter willful repeat infringement, Flama enforces a strict Three-Strike Repeat Infringer Policy:',
          '1. Strike 1: Formal written warning, takedown of infringing materials, and required re-acknowledgement of IP guidelines.',
          '2. Strike 2: Upon a second violation within 12 months, creator publishing privileges are suspended for thirty (30) days, alongside an interim freeze on associated payout disbursements.',
          '3. Strike 3: A third violation results in permanent revocation of seller privileges, forfeiture of revenue balances generated from infringing materials, and permanent user account closure.',
        ],
      },
    ],
  },

  'community-guidelines': {
    id: 'community-guidelines',
    title: 'Community Standards & Code of Conduct',
    officialBadge: 'Ethics & Supportive Learning Standards',
    lastUpdated: '13/09/2026',
    effectiveDate: '15/09/2026',
    version: 'v2.0',
    readTimeMinutes: 12,
    executiveSummary:
      'Flama Community Standards establish ethical boundaries and safety requirements for all learners and creators. This policy specifically addresses prohibitions against malicious code injection within study cards, automated data scraping, toxic behavior, and ticketed dispute resolution via support channels.',
    clauses: [
      {
        id: 'clause-comm-mission',
        clauseNumber: 'Article 1',
        title: 'Community Mission & Supportive Learning Tenets',
        summary: 'Cultivating a civilized, safe, respectful, and constructive knowledge retention environment.',
        content: [
          'Flama strives to be an inspiring, civilized, and comprehensive multidisciplinary learning platform. We believe optimal knowledge acquisition thrives only within an environment founded on mutual respect, diversity, and supportive collaboration.',
          'All users participating in the Flama platform are expected to interact civilly across study card contents, comments, change requests, and communications with support personnel.',
        ],
      },
      {
        id: 'clause-comm-flashcard-security',
        clauseNumber: 'Article 2',
        title: 'Technical Flashcard Security Standards (Defense-in-Depth)',
        summary: 'Four layers of XSS defense and strict regulations governing HTML and styling within study cards.',
        content: [
          'Flama enables rich study card formatting including phonetic annotations, multimodal text, audio clips, and structured styling. However, exploiting cards to introduce malicious code is strictly prohibited.',
        ],
        subClauses: [
          {
            id: 'comm-2-1',
            clauseNumber: '2.1',
            title: 'Flama Multi-Layer Defense-in-Depth Architecture',
            content: [
              'To ensure the safety of all learners, Flama enforces an industry-standard multi-layer security architecture:',
              '1. Server-Side Layer: Multi-tier sanitization engines on the server automatically strip dangerous script constructs (<script>, <iframe>, <object>, <embed>, <form>, <link>) and allow solely a safe whitelist of attributes.',
              '2. Browser Client Layer: Automated HTML sanitization before DOM rendering on learner study interfaces.',
              '3. Isolated Execution Layer: Card faces render within isolated sandbox frames, preventing unauthorized inspection of session cookies, security tokens, or manipulation of the host application window.',
              '4. Network Security Layer: Strict Content Security Policies prevent unauthorized external data exfiltration.',
            ],
          },
          {
            id: 'comm-2-2',
            clauseNumber: '2.2',
            title: 'Strict Prohibition on Malicious Scripts & Exploit Probing',
            content: [
              'Users must never attempt to bypass sanitization filters, embed dangerous JavaScript expressions, insert event handlers outside permitted audio triggers, embed tracking pixels, or deliberately induce browser freezing for other learners.',
            ],
          },
        ],
        callout: {
          type: 'warning',
          label: 'Sanctions for Intentional Malware Injection',
          text: 'Any user who deliberately crafts or disseminates study cards containing exploit payloads designed to compromise learner data will face immediate permanent account termination without prior notice.',
        },
      },
      {
        id: 'clause-comm-scraping',
        clauseNumber: 'Article 3',
        title: 'Prohibition of Automated Scraping & Fraudulent Conduct',
        summary: 'Ban on automated crawlers, API rate limits, and prohibition of simulated study metric tampering.',
        content: [
          'Flama’s learning content resources and API services are designed to serve authentic human educational progress.',
        ],
        subClauses: [
          {
            id: 'comm-3-1',
            clauseNumber: '3.1',
            title: 'Anti-Scraping Policy',
            content: [
              'Users may not deploy automated software, bots, spiders, crawlers, web scrapers, or background scripts to harvest learning databases, user profiles, or Marketplace assets without express authorization.',
            ],
          },
          {
            id: 'comm-3-2',
            clauseNumber: '3.2',
            title: 'API Rate Limits & Connection Throttling',
            content: [
              'Automated monitoring applies fair daily and per-minute request limits to guarantee balanced system resources for all learners. Excessive traffic surges will trigger automated connection throttling and temporary disconnection, with persistent abuse leading to permanent access restriction.',
            ],
          },
          {
            id: 'comm-3-3',
            clauseNumber: '3.3',
            title: 'Prohibition of Study Metric Cheating',
            content: [
              'Automated tools designed to simulate card review sessions to falsify retention statistics, study streaks, or leaderboard standings are strictly banned.',
            ],
          },
        ],
      },
      {
        id: 'clause-comm-prohibitions',
        clauseNumber: 'Article 4',
        title: 'Strictly Prohibited Content Platform-Wide',
        summary: 'Catalog of illegal, obscene, hateful, harassing, and promotional spam content.',
        content: [
          'Flama enforces a zero-tolerance policy against the following prohibited materials across all platform surfaces (deck titles, card content, discussions, usernames, support tickets):',
          '1. Unlawful Content: Propaganda inciting anti-state activities, violence, weapons or narcotics trafficking, or instructions facilitating criminal conduct.',
          '2. Obscene & Sexually Explicit Content: Sharing pornographic, sexually explicit, exploitative, or indecent images, audio, or texts.',
          '3. Hate Speech & Harassment: Defamation, cyberbullying, menacing threats, or discrimination based on race, religion, gender, or background.',
          '4. Phishing & Spam: Distributing deceptive phishing links, coupon spam, gambling promotions, or non-educational commercial advertisements.',
        ],
      },
      {
        id: 'clause-comm-enforcement',
        clauseNumber: 'Article 5',
        title: 'Violation Reporting & Support Ticket Channel',
        summary: 'Reporting workflow via standardized ticket identifier TK-YYYYMMDD-XXXXXX and tiered sanctions.',
        content: [
          'To uphold community integrity, all members have the right and responsibility to report violations:',
        ],
        subClauses: [
          {
            id: 'comm-5-1',
            clauseNumber: '5.1',
            title: 'Reporting Workflow via Support Tickets',
            content: [
              'Learners can submit violation reports within the application at the Support page (/support) or via our online intake desk. Each report is assigned a unique tracking identifier with the format: `TK-YYYYMMDD-XXXXXX`.',
              'The Flama moderation team commits to reviewing and processing reports within forty-eight (48) business hours of submission.',
            ],
          },
          {
            id: 'comm-5-2',
            clauseNumber: '5.2',
            title: 'Tiered Disciplinary Scale',
            content: [
              'Depending on severity and violation history, Flama enforces progressive disciplinary sanctions:',
              'Level 1 (Notice): Email advisory with a requirement to amend or remove improper content.',
              'Level 2 (Suspension): Temporary restriction of publishing capabilities, commenting privileges, or account access for 7 to 30 days.',
              'Level 3 (Permanent Termination): Irreversible account deletion, IP blocking, and referral to law enforcement authorities for grave legal breaches.',
            ],
          },
        ],
      },
    ],
  },

  cookies: {
    id: 'cookies',
    title: 'Cookie & Local Storage Policy',
    officialBadge: 'Storage Technology Transparency',
    lastUpdated: '13/09/2026',
    effectiveDate: '15/09/2026',
    version: 'v2.0',
    readTimeMinutes: 8,
    executiveSummary:
      'This policy details how Flama utilizes strictly necessary session cookies and browser LocalStorage on your device. Flama respects learner privacy and affirms a complete absence of third-party advertising tracking cookies.',
    clauses: [
      {
        id: 'clause-cookie-definition',
        clauseNumber: 'Article 1',
        title: 'Concept of Cookies & Local Storage Technology',
        summary: 'Definitions of cookie files and browser Web Storage technology.',
        content: [
          'Cookies are compact text files stored within your browser environment when accessing services. Web Storage technologies (LocalStorage and SessionStorage) enable the platform to retain interface preferences directly within your browser without requiring continuous server queries during navigation.',
        ],
      },
      {
        id: 'clause-cookie-essential',
        clauseNumber: 'Article 2',
        title: 'Strictly Necessary Essential Cookies Catalog',
        summary: 'Essential cookies strictly required to maintain secure authentication and defend against CSRF attacks.',
        content: [
          'Flama utilizes solely essential cookies directly required for platform security and core operation:',
          '1. Session Cookie: Operates via secure authentication tokens allowing the system to recognize authenticated users as they navigate between study pages. This cookie is hardened with industry standards: `HttpOnly` (preventing script access), `SameSite=Lax` (defending against request forgery), and `Secure` (transmitted exclusively over encrypted HTTPS connections).',
          '2. CSRF Protection Cookie: Contains a cryptographically random token safeguarding your account against Cross-Site Request Forgery during card updates or payment checkout.',
        ],
        callout: {
          type: 'info',
          label: 'Commitment to Zero Third-Party Advertising Trackers',
          text: 'Flama NEVER employs third-party advertising tracking cookies and never sells or transmits browsing telemetry to commercial advertising networks.',
        },
      },
      {
        id: 'clause-cookie-storage',
        clauseNumber: 'Article 3',
        title: 'Application of Local Storage (LocalStorage / SessionStorage)',
        summary: 'Persistence of light/dark theme, table layout widths, and Flama Audio pairing tokens.',
        content: [
          'We employ local browser storage to deliver a fluid learning experience:',
          '1. UI Preferences: Retaining Light / Dark color theme choices and customized column widths in personal study tables.',
          '2. Study Settings: Remembering audio volume preferences, default speech playback rates, and preferred synthetic voice selections.',
          '3. Flama Audio Pairing: Storing secure pairing authentication tokens facilitating communication between the browser and the desktop companion application.',
        ],
      },
      {
        id: 'clause-cookie-management',
        clauseNumber: 'Article 4',
        title: 'Learner Rights to Manage & Disable Cookies',
        summary: 'Guidance on browser cookie controls and the operational consequences of blocking session cookies.',
        content: [
          'You maintain complete discretion to control, decline, or clear stored cookies through your browser privacy settings (Google Chrome, Microsoft Edge, Mozilla Firefox, Apple Safari).',
          'Please note that because Flama cookies are strictly necessary for session security, disabling all cookies will prevent the system from maintaining authenticated status and disable personalized study features.',
        ],
      },
    ],
  },
}

export const legalDocumentsEnList: LegalDocument[] = Object.values(legalDocumentsEn)
