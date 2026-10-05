/**
 * J.A.R.V.I.S. Volumetric Hologram Engine
 * Authentic Movie Holographic Core with Silky-Smooth Fluid Wave Formation & Acoustic Vibration
 * Powered by Three.js
 */

(function () {
  'use strict';

  if (typeof THREE === 'undefined') {
    console.error('Three.js library is required for J.A.R.V.I.S. Hologram');
    return;
  }

  let scene, camera, renderer;
  let container, canvas;
  let hologramGroup, coreGroup, ringsGroup, particlesGroup, sweepGroup, avengersGroup;
  let waveInner, waveOuter, waveRipples;
  let animId = null;

  // Raycasting & Avengers 3D Interaction
  let raycaster, mouse;
  let avengerMeshes = [];
  let hoveredAvenger = null;
  let mouseDownX = 0, mouseDownY = 0;

  // Marvel Avengers Database (Stark Industries Archives Protocol)
  const AVENGERS_ROSTER = [
    {
      id: 'iron_man',
      name: 'TONY STARK',
      alias: 'IRON MAN',
      color: '#f59e0b',
      accentColor: '#ef4444',
      threat: 'LEVEL 10 ALPHA',
      clearance: 'STARK LEVEL 9 PRIME',
      affiliation: 'AVENGERS FOUNDER // STARK IND.',
      suit: 'MARK LXXXV (NANOTECH PRIME)',
      reactor: 'RT-07 ARC REACTOR (8 GJ/SEC)',
      stats: {
        intelligence: 100,
        technology: 100,
        combat: 85,
        energy: 95,
        agility: 80,
      },
      equipment: [
        'Mark 85 Nanotech Armor with Morphing Nanoparticles',
        'Repulsor Beams & Unibeam Chest Cannon',
        'Energy Blade, Micro-Missiles & Nano Shield',
        'F.R.I.D.A.Y. & J.A.R.V.I.S. Core Neural Sync',
      ],
      bio: 'Genius, billionaire, playboy, philanthropist. Co-founder of the Avengers and architect of Earth’s planetary defense systems. Pioneered the time navigation GPS enabling the Temporal Heist, and sacrificed himself using the Stark Nano-Gauntlet to eliminate Thanos and his army, saving the entire universe.',
      feats: [
        'Invented miniaturized Arc Reactor in a cave in Afghanistan',
        'Intercepted nuclear warhead through the Chitauri wormhole (New York)',
        'Built Hulkbuster and Ultron Global Defense systems',
        'Designed Time Travel Quantum Tunnel & Stark Nano-Gauntlet',
      ],
      audioSummary: 'Tony Stark, codename Iron Man. Supreme commander of Stark Industries and creator of the Mark series tactical suits. Equipped with Mark 85 nanotech armor and 8 gigajoule arc reactor.',
    },
    {
      id: 'captain_america',
      name: 'STEVE ROGERS',
      alias: 'CAPTAIN AMERICA',
      color: '#3b82f6',
      accentColor: '#f87171',
      threat: 'LEVEL 9 TACTICAL',
      clearance: 'S.H.I.E.L.D. LEVEL 8',
      affiliation: 'AVENGERS LEADER // S.H.I.E.L.D.',
      suit: 'TACTICAL STEALTH VIBRANIUM WEAVE',
      reactor: 'VITA-RAY ENHANCED CELLULAR CORE',
      stats: {
        intelligence: 85,
        technology: 65,
        combat: 100,
        energy: 70,
        agility: 92,
      },
      equipment: [
        'Pure Vibranium Kinetic-Absorption Shield',
        'Mjolnir Asgardian Hammer (Worthy Wielder)',
        'Reinforced Kevlar-Vibranium Composite Uniform',
        'Tactical S.H.I.E.L.D. Communications Array',
      ],
      bio: 'The First Avenger and peerless field tactician. Enhanced to the absolute peak of human physical potential by Dr. Erskine’s Super-Soldier Serum. Led Allied forces against Hydra in WWII, commanded the Avengers through the Battle of New York and the Sokovia Incident, and wielded Mjolnir in the Battle of Earth.',
      feats: [
        'Defeated the Red Skull and dismantled Hydra WWII war machines',
        'Led Avengers tactical strike teams against Chitauri invaders',
        'Wielded Mjolnir and unleashed divine lightning against Thanos',
        'Returned all six Infinity Stones to their original timelines',
      ],
      audioSummary: 'Captain Steve Rogers, The First Avenger. S.H.I.E.L.D. level eight operative. Master of vibranium shield kinetic combat and proven worthy wielder of Mjolnir.',
    },
    {
      id: 'thor',
      name: 'THOR ODINSON',
      alias: 'GOD OF THUNDER',
      color: '#06b6d4',
      accentColor: '#a855f7',
      threat: 'LEVEL 10 OMEGA',
      clearance: 'ASGARDIAN ROYAL CROWN',
      affiliation: 'AVENGERS // ASGARD',
      suit: 'DIVINE ASGARDIAN URU ARMOR',
      reactor: 'COSMIC LIGHTNING SINGULARITY',
      stats: {
        intelligence: 75,
        technology: 70,
        combat: 95,
        energy: 100,
        agility: 88,
      },
      equipment: [
        'Stormbreaker (Bifrost-Channeling King’s Axe)',
        'Mjolnir (Enchanted Uru Hammer)',
        'Asgardian Chainmail & Crimson Cape',
        'God of Thunder Divine Lightning Manipulation',
      ],
      bio: 'Crown Prince of Asgard and God of Thunder. Over 1,500 years of cosmic warfare experience. Channels raw celestial lightning without needing a conduit. Traveled to Nidavellir with Rocket and Groot to forge Stormbreaker in the heart of a dying star, turning the tide of the Battle of Wakanda.',
      feats: [
        'Forged Stormbreaker in the full blazing focus of a neutron star',
        'Turned the tide of the Battle of Wakanda single-handedly',
        'Summons the Bifrost for instant interdimensional travel',
        'Stood toe-to-toe with the Mad Titan Thanos',
      ],
      audioSummary: 'Thor Odinson, God of Thunder. Omega-level Asgardian deity wielding the king-killer axe Stormbreaker. Capable of summoning the Bifrost and directing cosmic electrical tempests.',
    },
    {
      id: 'hulk',
      name: 'BRUCE BANNER',
      alias: 'THE INCREDIBLE HULK',
      color: '#10b981',
      accentColor: '#22c55e',
      threat: 'LEVEL 10 CATACLYSM',
      clearance: 'S.H.I.E.L.D. LEVEL 8',
      affiliation: 'AVENGERS // CULVER UNIVERSITY',
      suit: 'GAMMA-RESISTANT STRETCH WEAVE',
      reactor: 'BIO-GAMMA CELLULAR FURNACE',
      stats: {
        intelligence: 98,
        technology: 92,
        combat: 95,
        energy: 90,
        agility: 75,
      },
      equipment: [
        'Stark Industries Nano-Gauntlet Conduit',
        'Gamma Spectroscopy Telemetry Array',
        'Indestructible Kinetic Shock Absorption',
        'Smart Hulk Neuro-Synaptic Harmony Matrix',
      ],
      bio: 'Dr. Bruce Banner holds seven PhDs and is Earth’s foremost expert on nuclear physics and gamma radiation. Transformed by gamma catastrophe into the Hulk. In the post-Blip era, Banner merged brains and brawn into Smart Hulk, performing the cosmic reversal snap that restored trillions of lives.',
      feats: [
        'Executed the Universal Reversal Snap using the Nano Gauntlet',
        'Survived lethal gamma radiation surges from six Infinity Stones',
        'Single-handedly brought down a Leviathan in New York',
        'Co-engineered the Vision synthesis and Quantum Tunnel',
      ],
      audioSummary: 'Doctor Bruce Banner, Smart Hulk. Cataclysm-grade strength matched with seven doctorates. The only biological entity capable of withstanding the raw energy of all six Infinity Stones.',
    },
    {
      id: 'black_widow',
      name: 'NATASHA ROMANOFF',
      alias: 'BLACK WIDOW',
      color: '#ef4444',
      accentColor: '#0284c7',
      threat: 'LEVEL 8 INFILTRATION',
      clearance: 'S.H.I.E.L.D. LEVEL 9',
      affiliation: 'AVENGERS // S.H.I.E.L.D. // KGB',
      suit: 'TACTICAL REINFORCED STEALTH SUIT',
      reactor: 'BIO-ENHANCED AGILITY CORE',
      stats: {
        intelligence: 92,
        technology: 80,
        combat: 98,
        energy: 60,
        agility: 99,
      },
      equipment: [
        'Widow’s Bite Electro-Shock Wrist Gauntlets',
        'Dual Electro-Shock Tactical Batons',
        'Glock 26 Handguns & Grappling Wire',
        'Stark Micro-EMP & Holographic Disguise Matrix',
      ],
      bio: 'Top-tier master of espionage, tactical infiltration, and martial combat. Trained in the elite Soviet Red Room before defecting to S.H.I.E.L.D. Became the central glue holding the Avengers together during the darkest hours after the Decimation, and secured the Soul Stone on Vormir.',
      feats: [
        'Exposed Hydra infiltration inside S.H.I.E.L.D. and leaked classified files',
        'Kept global Avengers network operating during the five-year Blip',
        'Secured the Soul Stone on Vormir for the Time Heist',
        'Dismantled the global Red Room assassin network',
      ],
      audioSummary: 'Natasha Romanoff, Black Widow. Highest-clearance S.H.I.E.L.D. intelligence operative. Master of close-quarters combat, stealth infiltration, and tactical coordination.',
    },
    {
      id: 'spiderman',
      name: 'PETER PARKER',
      alias: 'SPIDER-MAN',
      color: '#ef4444',
      accentColor: '#3b82f6',
      threat: 'LEVEL 8 TACTICAL VANGUARD',
      clearance: 'STARK PROTOCOL LEVEL 7',
      affiliation: 'AVENGERS // QUEENS VANGUARD',
      suit: 'STARK IRON SPIDER (MODEL A17-N)',
      reactor: 'NEURAL WEB NANO-CORE',
      stats: {
        intelligence: 90,
        technology: 85,
        combat: 88,
        energy: 70,
        agility: 100,
      },
      equipment: [
        'Stark Iron Spider Nanotech Suit with Waldoes (4 Arms)',
        'Custom Synthetic Web-Shooters (Multiple Web Types)',
        'Precognitive Spider-Sense Reflex Matrix',
        'Instant-Kill Combat Mode & Holographic HUD',
      ],
      bio: 'Queens high school prodigy recruited and mentored by Tony Stark. Possesses proportional strength and agility of a spider, Wall-Crawling capability, and a precognitive Spider-Sense danger alert. Fought in the airport clash in Germany, boarded the Black Order Q-Ship, and defended the Stark Nano-Gauntlet.',
      feats: [
        'Helped defeat Ebony Maw in deep space aboard the alien Q-Ship',
        'Safely shielded and transported the Infinity Gauntlet across the battlefield',
        'Synthesized high-tensile web fluids and solved Stark quantum algorithms',
        'Defeated the Vulture and Mysterio utilizing sensory precision',
      ],
      audioSummary: 'Peter Parker, Spider-Man. Stark Industries protege equipped with the Mark seventeen nanotech Iron Spider suit. Unrivaled agility, web ballistics, and precognitive sensory reflexes.',
    },
    {
      id: 'doctor_strange',
      name: 'STEPHEN STRANGE',
      alias: 'DOCTOR STRANGE',
      color: '#f59e0b',
      accentColor: '#10b981',
      threat: 'LEVEL 10 MYSTIC GUARDIAN',
      clearance: 'MASTERS OF THE MYSTIC ARTS',
      affiliation: 'AVENGERS // SANCTUM SANCTORUM',
      suit: 'SORCERER SUPREME TACTICAL VESTMENTS',
      reactor: 'ELDRITCH ENERGY DIMENSIONAL WEAVE',
      stats: {
        intelligence: 96,
        technology: 75,
        combat: 90,
        energy: 100,
        agility: 82,
      },
      equipment: [
        'Cloak of Levitation (Sentient Relic)',
        'Eye of Agamotto / Time Manipulation Sigils',
        'Sling Ring (Interdimensional Portal Conduit)',
        'Eldritch Tao Mandalas & Mirror Dimension Bending',
      ],
      bio: 'Former world-renowned neurosurgeon who unlocked the cosmic secrets of the Mystic Arts at Kamar-Taj. Master of dimensional energy manipulation, time warping, and reality bending. Witnessed 14,000,605 future timelines on Titan, correctly orchestrating the singular sequence that delivered ultimate victory.',
      feats: [
        'Analyzed 14,000,605 future timelines to engineer the winning path',
        'Trapped Dormammu in a temporal paradox to save Earth',
        'Conjured portals transporting all resurrected armies to the final battle',
        'Held back a raging tidal wave to protect the Avengers compound',
      ],
      audioSummary: 'Doctor Stephen Strange, Master of the Mystic Arts and guardian of the New York Sanctum. Master of dimensional physics, mirror reality distortion, and eldritch energy manipulation.',
    },
  ];

  window.AVENGERS_ROSTER = AVENGERS_ROSTER;

  // Fluid Wave & Speech Resonance State
  let isSpeaking = false;
  let targetWaveEnergy = 0;
  let currentWaveEnergy = 0;
  let speechCadence = 0;
  let wavePhase = 0;

  // Continuous Cinematic 360° All-Sides 3D Rotation
  let isDragging = false;
  let dragButton = 0; // 0: left, 2: right
  let prevMouseX = 0;
  let prevMouseY = 0;
  let targetRotationX = 0.12;
  let targetRotationY = 0.25;
  let targetRotationZ = 0;
  let currentRotationX = 0.12;
  let currentRotationY = 0.25;
  let currentRotationZ = 0;
  let momentumX = 0;
  let momentumY = 0;
  let autoOrbit = true;
  let targetCameraZ = 48;
  let currentCameraZ = 48;

  // Soft circular particle texture cache (Prevents ugly square white boxes in WebGL)
  let cachedPointTexture = null;
  function getCircleTexture() {
    if (cachedPointTexture) return cachedPointTexture;
    const pCanvas = document.createElement('canvas');
    pCanvas.width = 64;
    pCanvas.height = 64;
    const pCtx = pCanvas.getContext('2d');
    const grad = pCtx.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
    grad.addColorStop(0.3, 'rgba(0, 240, 255, 0.85)');
    grad.addColorStop(0.7, 'rgba(0, 240, 255, 0.2)');
    grad.addColorStop(1, 'rgba(0, 240, 255, 0)');
    pCtx.fillStyle = grad;
    pCtx.beginPath();
    pCtx.arc(32, 32, 32, 0, Math.PI * 2);
    pCtx.fill();
    cachedPointTexture = new THREE.CanvasTexture(pCanvas);
    return cachedPointTexture;
  }

  // Ultra-Smooth Waveform Vertices (High resolution for pure trigonometric fluidity)
  const WAVE_SEGMENTS = 192;
  let innerPositions, innerGeometry;
  let outerPositions, outerGeometry;

  function init() {
    container = document.getElementById('jarvisHoloContainer');
    canvas = document.getElementById('jarvisHoloCanvas');
    if (!container || !canvas) return;

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    // Scene
    scene = new THREE.Scene();

    // Camera (Ultra-wide near/far clipping planes for infinite zoom depth)
    camera = new THREE.PerspectiveCamera(40, width / height, 0.001, 150000);
    camera.position.set(0, 0, 48);

    // Renderer
    renderer = new THREE.WebGLRenderer({
      canvas: canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    // Master Hologram Group
    hologramGroup = new THREE.Group();
    hologramGroup.position.set(0, 0.5, 0);
    scene.add(hologramGroup);

    // Sub-groups
    coreGroup = new THREE.Group();
    avengersGroup = new THREE.Group();
    ringsGroup = new THREE.Group();
    particlesGroup = new THREE.Group();
    sweepGroup = new THREE.Group();
    waveRipples = new THREE.Group();

    hologramGroup.add(coreGroup);
    hologramGroup.add(avengersGroup);
    hologramGroup.add(ringsGroup);
    hologramGroup.add(particlesGroup);
    hologramGroup.add(sweepGroup);
    hologramGroup.add(waveRipples);

    // Raycaster for 3D interactions
    raycaster = new THREE.Raycaster();
    mouse = new THREE.Vector2();

    // Build Volumetric Holographic Architecture
    buildCore();
    buildAvengersRing();
    buildGimbalRings();
    buildParticleMatrix();
    buildFluidWaveforms();
    buildRadarSweep();

    // Event Listeners
    setupEvents();

    // Start Animation Loop
    animate(0);
  }

  // 1. Central Stark Arc Reactor Holographic Core (No white boxes or solid spheres)
  function buildCore() {
    // Mini Arc Reactor Inner Core Ring
    const innerRingGeo = new THREE.RingGeometry(0.65, 0.88, 36);
    const innerRingMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
    });
    const innerRing = new THREE.Mesh(innerRingGeo, innerRingMat);
    coreGroup.add(innerRing);

    // Secondary Gold Reactor Housing Ring
    const goldRingGeo = new THREE.RingGeometry(1.05, 1.18, 36);
    const goldRingMat = new THREE.MeshBasicMaterial({
      color: 0xf59e0b,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending,
    });
    const goldRing = new THREE.Mesh(goldRingGeo, goldRingMat);
    coreGroup.add(goldRing);

    // Rotating icosahedral cybernetic core
    const icoGeo = new THREE.IcosahedronGeometry(2.0, 1);
    const icoMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      wireframe: true,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
    });
    const icoMesh = new THREE.Mesh(icoGeo, icoMat);
    icoMesh.name = 'icoMesh';
    coreGroup.add(icoMesh);

    // Cyan plasma corona
    const coronaGeo = new THREE.SphereGeometry(2.8, 24, 24);
    const coronaMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
      wireframe: true,
      side: THREE.DoubleSide,
    });
    const corona = new THREE.Mesh(coronaGeo, coronaMat);
    corona.name = 'corona';
    coreGroup.add(corona);

    // Subtle atmospheric blue halo
    const haloGeo = new THREE.SphereGeometry(4.2, 24, 24);
    const haloMat = new THREE.MeshBasicMaterial({
      color: 0x0284c7,
      transparent: true,
      opacity: 0.18,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
    });
    const halo = new THREE.Mesh(haloGeo, haloMat);
    halo.name = 'halo';
    coreGroup.add(halo);

    // Ambient point light
    const pLight = new THREE.PointLight(0x00f0ff, 3.8, 60);
    pLight.name = 'pLight';
    coreGroup.add(pLight);
  }

  // 1.5. 3D Marvel Avengers Holographic Database Carousel
  function buildAvengersRing() {
    avengerMeshes = [];
    const count = AVENGERS_ROSTER.length;
    const ringRadius = 3.8;

    AVENGERS_ROSTER.forEach((hero, idx) => {
      const angle = (idx / count) * Math.PI * 2;
      const x = Math.cos(angle) * ringRadius;
      const z = Math.sin(angle) * ringRadius;
      const y = Math.sin(angle * 2) * 0.45;

      const heroGroup = new THREE.Group();
      heroGroup.position.set(x, y, z);
      heroGroup.userData = {
        avengerId: hero.id,
        avenger: hero,
        origPosition: new THREE.Vector3(x, y, z),
      };

      // 1. Interactive Hologram Portrait Card
      const cardTex = createAvengerTexture(hero);
      const cardGeo = new THREE.PlaneGeometry(1.5, 1.5);
      const cardMat = new THREE.MeshBasicMaterial({
        map: cardTex,
        transparent: true,
        opacity: 0.95,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const cardMesh = new THREE.Mesh(cardGeo, cardMat);
      cardMesh.userData = { avengerId: hero.id, avenger: hero, parentGroup: heroGroup };
      heroGroup.add(cardMesh);
      avengerMeshes.push(cardMesh);

      // 2. Outer Holographic Glowing Reticle Ring
      const ringGeo = new THREE.RingGeometry(0.82, 0.88, 32);
      const ringMat = new THREE.MeshBasicMaterial({
        color: new THREE.Color(hero.color || '#00f0ff'),
        transparent: true,
        opacity: 0.65,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const ringMesh = new THREE.Mesh(ringGeo, ringMat);
      heroGroup.add(ringMesh);

      avengersGroup.add(heroGroup);
    });
  }

  // Procedural High-Definition Marvel Hero Emblem Canvas Texture
  function createAvengerTexture(hero) {
    const cvs = document.createElement('canvas');
    cvs.width = 256;
    cvs.height = 256;
    const ctx = cvs.getContext('2d');

    // 1. Deep translucent holographic backdrop circle
    ctx.clearRect(0, 0, 256, 256);
    ctx.beginPath();
    ctx.arc(128, 128, 120, 0, Math.PI * 2);
    const bgGrad = ctx.createRadialGradient(128, 128, 10, 128, 128, 120);
    bgGrad.addColorStop(0, 'rgba(10, 24, 48, 0.94)');
    bgGrad.addColorStop(0.75, 'rgba(4, 12, 28, 0.88)');
    bgGrad.addColorStop(1, 'rgba(0, 240, 255, 0.4)');
    ctx.fillStyle = bgGrad;
    ctx.fill();

    // 2. Neon Ring Border
    ctx.lineWidth = 4.5;
    ctx.strokeStyle = hero.color || '#00f0ff';
    ctx.shadowColor = hero.color || '#00f0ff';
    ctx.shadowBlur = 14;
    ctx.stroke();

    // 3. Cybernetic reticle tick marks around edge
    ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.lineWidth = 2;
    for (let a = 0; a < 8; a++) {
      const ang = (a / 8) * Math.PI * 2;
      const x1 = 128 + Math.cos(ang) * 110;
      const y1 = 128 + Math.sin(ang) * 110;
      const x2 = 128 + Math.cos(ang) * 122;
      const y2 = 128 + Math.sin(ang) * 122;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }

    // 4. Hero Specific Emblem / Iconography
    ctx.save();
    ctx.translate(128, 108);
    drawHeroEmblem(ctx, hero.id);
    ctx.restore();

    // 5. Hero Name Plate at Bottom
    ctx.fillStyle = 'rgba(2, 6, 23, 0.85)';
    ctx.fillRect(16, 188, 224, 34);
    ctx.strokeStyle = hero.color || '#00f0ff';
    ctx.lineWidth = 1.8;
    ctx.strokeRect(16, 188, 224, 34);

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 15px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = hero.color || '#00f0ff';
    ctx.shadowBlur = 8;
    ctx.fillText(hero.alias, 128, 205);

    const texture = new THREE.CanvasTexture(cvs);
    texture.minFilter = THREE.LinearFilter;
    return texture;
  }

  function drawHeroEmblem(ctx, heroId) {
    ctx.shadowBlur = 10;
    if (heroId === 'iron_man') {
      // Iron Man: Crimson & Gold Helmet Faceplate + Glowing Arc Reactor
      ctx.shadowColor = '#f59e0b';
      ctx.fillStyle = '#b91c1c';
      ctx.beginPath();
      ctx.moveTo(0, -52);
      ctx.bezierCurveTo(42, -52, 45, -10, 36, 22);
      ctx.lineTo(18, 44);
      ctx.lineTo(-18, 44);
      ctx.lineTo(-36, 22);
      ctx.bezierCurveTo(-45, -10, -42, -52, 0, -52);
      ctx.fill();

      // Gold faceplate
      ctx.fillStyle = '#f59e0b';
      ctx.beginPath();
      ctx.moveTo(0, -36);
      ctx.lineTo(26, -22);
      ctx.lineTo(22, 16);
      ctx.lineTo(10, 34);
      ctx.lineTo(-10, 34);
      ctx.lineTo(-22, 16);
      ctx.lineTo(-26, -22);
      ctx.closePath();
      ctx.fill();

      // Slit eyes glowing cyan
      ctx.shadowColor = '#00f0ff';
      ctx.shadowBlur = 15;
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(-20, -7, 14, 4.5);
      ctx.fillRect(6, -7, 14, 4.5);

      // Arc reactor dot
      ctx.beginPath();
      ctx.arc(0, 18, 6, 0, Math.PI * 2);
      ctx.fillStyle = '#00f0ff';
      ctx.fill();
    } else if (heroId === 'captain_america') {
      // Captain America: Concentric Vibranium Shield
      ctx.shadowColor = '#3b82f6';
      // Red ring
      ctx.fillStyle = '#dc2626';
      ctx.beginPath();
      ctx.arc(0, 0, 48, 0, Math.PI * 2);
      ctx.fill();
      // Silver ring
      ctx.fillStyle = '#e2e8f0';
      ctx.beginPath();
      ctx.arc(0, 0, 37, 0, Math.PI * 2);
      ctx.fill();
      // Red ring
      ctx.fillStyle = '#dc2626';
      ctx.beginPath();
      ctx.arc(0, 0, 26, 0, Math.PI * 2);
      ctx.fill();
      // Blue center
      ctx.fillStyle = '#2563eb';
      ctx.beginPath();
      ctx.arc(0, 0, 16, 0, Math.PI * 2);
      ctx.fill();
      // White Star
      ctx.shadowColor = '#ffffff';
      ctx.fillStyle = '#ffffff';
      drawStar(ctx, 0, 0, 5, 13, 5.5);
    } else if (heroId === 'thor') {
      // Thor: Winged Helm + Crackling Lightning
      ctx.shadowColor = '#06b6d4';
      ctx.fillStyle = '#94a3b8';
      // Helm dome
      ctx.beginPath();
      ctx.arc(0, -8, 28, Math.PI, 0);
      ctx.fill();
      // Wings
      ctx.fillStyle = '#e2e8f0';
      ctx.beginPath();
      ctx.moveTo(-26, -12);
      ctx.lineTo(-48, -42);
      ctx.lineTo(-30, -28);
      ctx.lineTo(-50, -12);
      ctx.lineTo(-26, 0);
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(26, -12);
      ctx.lineTo(48, -42);
      ctx.lineTo(30, -28);
      ctx.lineTo(50, -12);
      ctx.lineTo(26, 0);
      ctx.fill();

      // Glowing Lightning Bolt
      ctx.shadowColor = '#00f0ff';
      ctx.shadowBlur = 18;
      ctx.fillStyle = '#38bdf8';
      ctx.beginPath();
      ctx.moveTo(0, -32);
      ctx.lineTo(-12, 4);
      ctx.lineTo(2, 4);
      ctx.lineTo(-4, 38);
      ctx.lineTo(15, 0);
      ctx.lineTo(2, 0);
      ctx.closePath();
      ctx.fill();
    } else if (heroId === 'hulk') {
      // Hulk: Mighty Gamma Fist with Radioactive Glow
      ctx.shadowColor = '#10b981';
      ctx.fillStyle = '#059669';
      // Clenched fist
      ctx.beginPath();
      ctx.roundRect(-28, -24, 56, 42, 10);
      ctx.fill();
      // Thumb
      ctx.beginPath();
      ctx.roundRect(-38, -4, 16, 22, 7);
      ctx.fill();
      // Knuckle grooves
      ctx.strokeStyle = '#022c22';
      ctx.lineWidth = 2.5;
      for (let k = -14; k <= 14; k += 9) {
        ctx.beginPath();
        ctx.moveTo(k, -24);
        ctx.lineTo(k, 4);
        ctx.stroke();
      }
      // Gamma energy spikes
      ctx.strokeStyle = '#34d399';
      ctx.lineWidth = 2.5;
      ctx.shadowBlur = 15;
      ctx.shadowColor = '#34d399';
      for (let s = 0; s < 6; s++) {
        const rad = (s / 6) * Math.PI * 2;
        ctx.beginPath();
        ctx.moveTo(Math.cos(rad) * 34, Math.sin(rad) * 34);
        ctx.lineTo(Math.cos(rad) * 48, Math.sin(rad) * 48);
        ctx.stroke();
      }
    } else if (heroId === 'black_widow') {
      // Black Widow: Red Hourglass Symbol + Crossed Stun Batons
      ctx.shadowColor = '#ef4444';
      ctx.strokeStyle = '#0284c7';
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.moveTo(-40, -40);
      ctx.lineTo(40, 40);
      ctx.moveTo(40, -40);
      ctx.lineTo(-40, 40);
      ctx.stroke();

      // Red Hourglass
      ctx.fillStyle = '#dc2626';
      ctx.shadowBlur = 16;
      ctx.shadowColor = '#ef4444';
      ctx.beginPath();
      ctx.moveTo(-20, -32);
      ctx.lineTo(20, -32);
      ctx.lineTo(0, 0);
      ctx.closePath();
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(-20, 32);
      ctx.lineTo(20, 32);
      ctx.closePath();
      ctx.fill();
    } else if (heroId === 'spiderman') {
      // Spider-Man: Mask & Web Pattern
      ctx.shadowColor = '#ef4444';
      ctx.fillStyle = '#dc2626';
      ctx.beginPath();
      ctx.ellipse(0, 0, 34, 44, 0, 0, Math.PI * 2);
      ctx.fill();

      // Web lines
      ctx.strokeStyle = '#1e1b4b';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(0, -44); ctx.lineTo(0, 44);
      ctx.moveTo(-34, 0); ctx.lineTo(34, 0);
      ctx.moveTo(-24, -28); ctx.lineTo(24, 28);
      ctx.moveTo(24, -28); ctx.lineTo(-24, 28);
      ctx.stroke();

      // Expressive white eyes with dark border
      ctx.shadowColor = '#ffffff';
      ctx.shadowBlur = 12;
      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = '#0f172a';
      ctx.lineWidth = 3.5;
      // Left eye
      ctx.beginPath();
      ctx.moveTo(-7, -10);
      ctx.lineTo(-28, -4);
      ctx.quadraticCurveTo(-20, 16, -5, 4);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      // Right eye
      ctx.beginPath();
      ctx.moveTo(7, -10);
      ctx.lineTo(28, -4);
      ctx.quadraticCurveTo(20, 16, 5, 4);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    } else if (heroId === 'doctor_strange') {
      // Doctor Strange: Eye of Agamotto & Eldritch Tao Mandala
      ctx.shadowColor = '#f59e0b';
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 2.5;
      ctx.shadowBlur = 14;
      ctx.beginPath();
      ctx.arc(0, 0, 42, 0, Math.PI * 2);
      ctx.stroke();
      ctx.strokeRect(-26, -26, 52, 52);

      // Eye of Agamotto
      ctx.fillStyle = '#b45309';
      ctx.beginPath();
      ctx.ellipse(0, 0, 24, 15, 0, 0, Math.PI * 2);
      ctx.fill();

      // Glowing Time Stone
      ctx.shadowColor = '#10b981';
      ctx.shadowBlur = 18;
      ctx.fillStyle = '#34d399';
      ctx.beginPath();
      ctx.arc(0, 0, 6.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function drawStar(ctx, cx, cy, spikes, outerRadius, innerRadius) {
    let rot = (Math.PI / 2) * 3;
    let x = cx;
    let y = cy;
    const step = Math.PI / spikes;

    ctx.beginPath();
    ctx.moveTo(cx, cy - outerRadius);
    for (let i = 0; i < spikes; i++) {
      x = cx + Math.cos(rot) * outerRadius;
      y = cy + Math.sin(rot) * outerRadius;
      ctx.lineTo(x, y);
      rot += step;

      x = cx + Math.cos(rot) * innerRadius;
      y = cy + Math.sin(rot) * innerRadius;
      ctx.lineTo(x, y);
      rot += step;
    }
    ctx.lineTo(cx, cy - outerRadius);
    ctx.closePath();
    ctx.fill();
  }

  // 2. Concentric Gyroscopic Gimbal Rings (Precision Stark Engineering)
  function buildGimbalRings() {
    const ringColors = [0x00f0ff, 0x38bdf8, 0x0284c7, 0x00f0ff];

    // Ring 1: Primary Equatorial Ring
    const r1Geo = new THREE.RingGeometry(7.2, 7.35, 96);
    const r1Mat = new THREE.MeshBasicMaterial({
      color: ringColors[0],
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
    });
    const r1 = new THREE.Mesh(r1Geo, r1Mat);
    r1.name = 'ring1';
    ringsGroup.add(r1);

    // Ring 2: Polar Ring (45° tilt)
    const r2Geo = new THREE.RingGeometry(9.2, 9.32, 96);
    const r2Mat = new THREE.MeshBasicMaterial({
      color: ringColors[1],
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending,
    });
    const r2 = new THREE.Mesh(r2Geo, r2Mat);
    r2.rotation.x = Math.PI / 4;
    r2.rotation.y = Math.PI / 8;
    r2.name = 'ring2';
    ringsGroup.add(r2);

    // Ring 3: Oblique Ring (-35° tilt)
    const r3Geo = new THREE.RingGeometry(11.2, 11.32, 96);
    const r3Mat = new THREE.MeshBasicMaterial({
      color: ringColors[2],
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
    });
    const r3 = new THREE.Mesh(r3Geo, r3Mat);
    r3.rotation.x = -Math.PI / 3;
    r3.rotation.z = Math.PI / 5;
    r3.name = 'ring3';
    ringsGroup.add(r3);

    // Ring 4: Outer HUD Reticle Ring with 36 Precision Tick Marks
    const r4Geo = new THREE.RingGeometry(13.4, 13.52, 96);
    const r4Mat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.5,
      blending: THREE.AdditiveBlending,
    });
    const r4 = new THREE.Mesh(r4Geo, r4Mat);
    r4.name = 'ring4';
    ringsGroup.add(r4);

    // Tick marks around outer ring
    for (let i = 0; i < 36; i++) {
      const angle = (i / 36) * Math.PI * 2;
      const isCardinal = i % 9 === 0;
      const length = isCardinal ? 1.1 : 0.45;
      const width = isCardinal ? 0.16 : 0.07;

      const tickGeo = new THREE.PlaneGeometry(width, length);
      const tickMat = new THREE.MeshBasicMaterial({
        color: isCardinal ? 0xffffff : 0x00f0ff,
        transparent: true,
        opacity: isCardinal ? 0.95 : 0.55,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
      });
      const tick = new THREE.Mesh(tickGeo, tickMat);
      tick.position.x = Math.cos(angle) * 14.1;
      tick.position.y = Math.sin(angle) * 14.1;
      tick.rotation.z = angle - Math.PI / 2;
      ringsGroup.add(tick);
    }
  }

  // 3. 3D Volumetric Neural Particle Constellation + Cosmic Starfield
  function buildParticleMatrix() {
    const coreCount = 600;
    const cosmicCount = 450;
    const totalCount = coreCount + cosmicCount;

    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(totalCount * 3);
    const colors = new Float32Array(totalCount * 3);

    // Core orbital shell (radius 10.5)
    const radius = 10.5;
    for (let i = 0; i < coreCount; i++) {
      const y = 1 - (i / (coreCount - 1)) * 2;
      const radiusAtY = Math.sqrt(1 - y * y);
      const theta = 2.39996323 * i;

      const x = Math.cos(theta) * radiusAtY;
      const z = Math.sin(theta) * radiusAtY;
      const r = radius + (Math.random() - 0.5) * 1.8;

      positions[i * 3] = x * r;
      positions[i * 3 + 1] = y * r;
      positions[i * 3 + 2] = z * r;

      if (i % 12 === 0) {
        colors[i * 3] = 1.0;
        colors[i * 3 + 1] = 0.85;
        colors[i * 3 + 2] = 0.35; // Gold accent
      } else {
        colors[i * 3] = 0.0;
        colors[i * 3 + 1] = 0.88 + Math.random() * 0.12;
        colors[i * 3 + 2] = 1.0; // Cyan
      }
    }

    // Outer cosmic constellation (radius 22 to 320 for majestic infinite zoom-out)
    for (let j = 0; j < cosmicCount; j++) {
      const idx = coreCount + j;
      const u = Math.random();
      const v = Math.random();
      const theta = u * 2.0 * Math.PI;
      const phi = Math.acos(2.0 * v - 1.0);
      const r = 22 + Math.pow(Math.random(), 1.6) * 300;
      const sinPhi = Math.sin(phi);

      positions[idx * 3] = r * sinPhi * Math.cos(theta);
      positions[idx * 3 + 1] = r * sinPhi * Math.sin(theta);
      positions[idx * 3 + 2] = r * Math.cos(phi);

      if (j % 9 === 0) {
        colors[idx * 3] = 1.0;
        colors[idx * 3 + 1] = 0.8;
        colors[idx * 3 + 2] = 0.4;
      } else {
        colors[idx * 3] = 0.0;
        colors[idx * 3 + 1] = 0.7 + Math.random() * 0.3;
        colors[idx * 3 + 2] = 1.0;
      }
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
      size: 0.48,
      map: getCircleTexture(),
      vertexColors: true,
      transparent: true,
      opacity: 0.88,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const particles = new THREE.Points(geometry, material);
    particles.name = 'particleMatrix';
    particlesGroup.add(particles);
  }

  // 4. Fluid Harmonic Waveform Rings (Dual concentric waves, pure organic fluid sine formation)
  function buildFluidWaveforms() {
    // Primary Inner Voice Wave (Radius ~ 5.6)
    innerGeometry = new THREE.BufferGeometry();
    innerPositions = new Float32Array((WAVE_SEGMENTS + 1) * 3);

    for (let i = 0; i <= WAVE_SEGMENTS; i++) {
      const theta = (i / WAVE_SEGMENTS) * Math.PI * 2;
      const r = 5.6;
      innerPositions[i * 3] = Math.cos(theta) * r;
      innerPositions[i * 3 + 1] = Math.sin(theta) * r;
      innerPositions[i * 3 + 2] = 0;
    }
    innerGeometry.setAttribute('position', new THREE.BufferAttribute(innerPositions, 3));

    const innerMat = new THREE.LineBasicMaterial({
      color: 0x00f0ff,
      linewidth: 2,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
    });
    waveInner = new THREE.Line(innerGeometry, innerMat);
    waveRipples.add(waveInner);

    // Secondary Outer Harmonic Wave (Radius ~ 8.2)
    outerGeometry = new THREE.BufferGeometry();
    outerPositions = new Float32Array((WAVE_SEGMENTS + 1) * 3);

    for (let i = 0; i <= WAVE_SEGMENTS; i++) {
      const theta = (i / WAVE_SEGMENTS) * Math.PI * 2;
      const r = 8.2;
      outerPositions[i * 3] = Math.cos(theta) * r;
      outerPositions[i * 3 + 1] = Math.sin(theta) * r;
      outerPositions[i * 3 + 2] = 0;
    }
    outerGeometry.setAttribute('position', new THREE.BufferAttribute(outerPositions, 3));

    const outerMat = new THREE.LineBasicMaterial({
      color: 0x38bdf8,
      linewidth: 1.5,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending,
    });
    waveOuter = new THREE.Line(outerGeometry, outerMat);
    waveRipples.add(waveOuter);
  }

  // 5. 360-Degree Radar Scanner Sweep
  function buildRadarSweep() {
    const sweepGeo = new THREE.BufferGeometry();
    const sweepPts = [];
    const count = 32;
    for (let i = 0; i <= count; i++) {
      const t = i / count;
      const angle = t * 0.45;
      sweepPts.push(0, 0, 0);
      sweepPts.push(Math.cos(angle) * 13.0, Math.sin(angle) * 13.0, 0);
    }
    sweepGeo.setAttribute('position', new THREE.Float32BufferAttribute(sweepPts, 3));
    const sweepMat = new THREE.LineBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.3,
      blending: THREE.AdditiveBlending,
    });
    const sweepLine = new THREE.LineSegments(sweepGeo, sweepMat);
    sweepLine.name = 'radarSweep';
    sweepGroup.add(sweepLine);
  }

  // Mouse & Touch Controls (Full 360° All-Sides Rotation & Zoom)
  function setupEvents() {
    if (!container) return;

    // Prevent default context menu on right click to allow 3D roll rotation
    container.addEventListener('contextmenu', (e) => {
      e.preventDefault();
    });

    container.addEventListener('mousedown', (e) => {
      isDragging = true;
      dragButton = e.button;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
      mouseDownX = e.clientX;
      mouseDownY = e.clientY;
      momentumX = 0;
      momentumY = 0;
      container.classList.add('grabbing');
    });

    container.addEventListener('click', (e) => {
      const dist = Math.hypot(e.clientX - mouseDownX, e.clientY - mouseDownY);
      if (dist < 8 && camera && avengerMeshes.length > 0) {
        // Clean click! Raycast into the 3D scene
        const rect = container.getBoundingClientRect();
        mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
        raycaster.setFromCamera(mouse, camera);

        const intersects = raycaster.intersectObjects(avengerMeshes, true);
        if (intersects.length > 0) {
          const hit = intersects[0].object;
          const heroId = hit.userData.avengerId;
          if (heroId && typeof window.openAvengerDossier === 'function') {
            window.openAvengerDossier(heroId);
            window.jarvisHolo.pulseWord(0.4);
          }
        }
      }
    });

    window.addEventListener('mouseup', () => {
      if (isDragging) {
        isDragging = false;
        container.classList.remove('grabbing');
      }
    });

    window.addEventListener('mousemove', (e) => {
      if (isDragging) {
        const deltaX = e.clientX - prevMouseX;
        const deltaY = e.clientY - prevMouseY;
        prevMouseX = e.clientX;
        prevMouseY = e.clientY;

        momentumY = deltaX * 0.008;
        momentumX = deltaY * 0.008;

        if (e.shiftKey || dragButton === 2) {
          // Roll around Z axis for full 6DOF tilt
          targetRotationZ += deltaX * 0.008;
          targetRotationX += deltaY * 0.008;
        } else {
          // Full unconstrained 360-degree rotation across X and Y
          targetRotationY += deltaX * 0.008;
          targetRotationX += deltaY * 0.008;
        }
      } else {
        const rect = container.getBoundingClientRect();
        if (
          e.clientX >= rect.left &&
          e.clientX <= rect.right &&
          e.clientY >= rect.top &&
          e.clientY <= rect.bottom
        ) {
          // Raycast hover detection on 3D Avengers cards
          mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
          mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
          if (camera && avengerMeshes.length > 0) {
            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(avengerMeshes, true);

            if (intersects.length > 0) {
              container.style.cursor = 'pointer';
              const hit = intersects[0].object;
              const targetGroup = hit.userData.parentGroup || hit;
              if (hoveredAvenger !== targetGroup) {
                if (hoveredAvenger) hoveredAvenger.scale.set(1.0, 1.0, 1.0);
                hoveredAvenger = targetGroup;
                if (hoveredAvenger) hoveredAvenger.scale.set(1.25, 1.25, 1.25);
              }
            } else {
              container.style.cursor = 'default';
              if (hoveredAvenger) {
                hoveredAvenger.scale.set(1.0, 1.0, 1.0);
                hoveredAvenger = null;
              }
            }
          }

          const normX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
          const normY = ((e.clientY - rect.top) / rect.height) * 2 - 1;
          targetRotationY += normX * 0.001;
          targetRotationX += -normY * 0.001;
        }
      }
    });

    // Touch Support with multi-touch pinch to zoom and 360 drag
    let touchStartDist = 0;
    container.addEventListener(
      'touchstart',
      (e) => {
        if (e.touches.length === 1) {
          isDragging = true;
          prevMouseX = e.touches[0].clientX;
          prevMouseY = e.touches[0].clientY;
          momentumX = 0;
          momentumY = 0;
        } else if (e.touches.length === 2) {
          const dx = e.touches[0].clientX - e.touches[1].clientX;
          const dy = e.touches[0].clientY - e.touches[1].clientY;
          touchStartDist = Math.hypot(dx, dy);
        }
      },
      { passive: true }
    );

    window.addEventListener('touchmove', (e) => {
      if (isDragging && e.touches.length === 1) {
        const deltaX = e.touches[0].clientX - prevMouseX;
        const deltaY = e.touches[0].clientY - prevMouseY;
        prevMouseX = e.touches[0].clientX;
        prevMouseY = e.touches[0].clientY;

        momentumY = deltaX * 0.008;
        momentumX = deltaY * 0.008;

        targetRotationY += deltaX * 0.008;
        targetRotationX += deltaY * 0.008;
      } else if (e.touches.length === 2) {
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const dist = Math.hypot(dx, dy);
        if (touchStartDist > 0 && dist > 10) {
          const ratio = touchStartDist / dist;
          targetCameraZ *= ratio;
          targetCameraZ = Math.max(0.015, Math.min(12000, targetCameraZ));
        }
        touchStartDist = dist;
      }
    });

    window.addEventListener('touchend', () => {
      if (isDragging) isDragging = false;
      touchStartDist = 0;
    });

    // Infinite-Range Exponential Zoom (From 0.015 subatomic quantum core to 12,000 cosmic infinity)
    container.addEventListener(
      'wheel',
      (e) => {
        e.preventDefault();
        const factor = Math.exp(e.deltaY * 0.0022);
        targetCameraZ *= factor;
        targetCameraZ = Math.max(0.015, Math.min(12000, targetCameraZ));
      },
      { passive: false }
    );

    // Double-click to toggle deep core inspection or standard overview
    container.addEventListener('dblclick', () => {
      if (targetCameraZ < 10) {
        targetCameraZ = 48; // Reset to standard cinematic view
      } else if (targetCameraZ > 120) {
        targetCameraZ = 48; // Reset to standard cinematic view
      } else {
        targetCameraZ = 0.12; // Dive deep into quantum infinite core
      }
    });

    window.addEventListener('resize', onWindowResize);
  }

  function onWindowResize() {
    if (!container || !renderer || !camera) return;
    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }

  // Animation Loop: 360° All-Sides Rotation + Calm, Majestic Slow Wave Formation & Subtle Resonance
  function animate(time) {
    animId = requestAnimationFrame(animate);

    const t = time * 0.001;
    wavePhase += 0.012; // Slow, majestic wave progression

    // Unconstrained 360° All-Sides Rotation Momentum & Auto-Orbit
    if (!isDragging) {
      if (autoOrbit) {
        targetRotationY += 0.0035; // Continuous smooth 360° horizontal rotation
        targetRotationX += Math.sin(t * 0.4) * 0.001; // Gentle 3D spherical bobbing showing top and bottom
      }
      targetRotationY += momentumY;
      targetRotationX += momentumX;
      momentumY *= 0.94;
      momentumX *= 0.94;
    }

    currentRotationX += (targetRotationX - currentRotationX) * 0.07;
    currentRotationY += (targetRotationY - currentRotationY) * 0.07;
    currentRotationZ += (targetRotationZ - currentRotationZ) * 0.07;

    // Scale-Invariant Logarithmic Geometric Zoom Interpolation
    // Moves seamlessly at equal perceptual zoom speeds whether at 0.015 or 12,000
    const safeCur = Math.max(0.005, currentCameraZ);
    const safeTar = Math.max(0.005, targetCameraZ);
    const logCur = Math.log(safeCur);
    const logTar = Math.log(safeTar);
    currentCameraZ = Math.exp(logCur + (logTar - logCur) * 0.12);

    if (camera) {
      camera.position.z = currentCameraZ;
      // Dynamically adjust near plane so geometry is never clipped when deep in the quantum core
      camera.near = Math.min(0.005, currentCameraZ * 0.05);
      camera.far = Math.max(15000, currentCameraZ * 12);
      camera.updateProjectionMatrix();
    }

    // Smooth Slow Energy Damping (Gentle ease-out)
    currentWaveEnergy += (targetWaveEnergy - currentWaveEnergy) * 0.06;
    targetWaveEnergy *= 0.96;
    if (targetWaveEnergy < 0.001) targetWaveEnergy = 0;

    // Slow, deep vocal cadence when speaking (Natural organic swell)
    if (isSpeaking) {
      const vocalHarmonic = Math.sin(t * 3.2) * 0.25 + Math.sin(t * 1.8) * 0.2 + 0.45;
      speechCadence += (vocalHarmonic - speechCadence) * 0.08;
    } else {
      speechCadence *= 0.92;
    }

    const totalEnergy = Math.max(0.06, currentWaveEnergy + speechCadence);

    // Calm, Majestic Volumetric Levitation with 360° all-sides orientation
    if (hologramGroup) {
      hologramGroup.rotation.x = currentRotationX;
      hologramGroup.rotation.y = currentRotationY;
      hologramGroup.rotation.z = currentRotationZ;

      // Slow, steady cinematic floating breath
      const levitation = Math.sin(t * 1.4) * 0.35;
      hologramGroup.position.x = 0;
      hologramGroup.position.y = 0.5 + levitation;
    }

    // 3D Marvel Avengers Holographic Orbit & Dynamic Billboarding
    if (avengersGroup) {
      avengersGroup.rotation.y = t * 0.16;
      avengersGroup.children.forEach((child) => {
        if (child && child.userData && child.userData.avengerId && camera) {
          child.quaternion.copy(camera.quaternion);
        }
      });
    }

    // Gimbal Rings Harmonic Rotations (Smooth & slow)
    if (ringsGroup) {
      const r1 = ringsGroup.getObjectByName('ring1');
      if (r1) r1.rotation.z = -t * 0.28;

      const r2 = ringsGroup.getObjectByName('ring2');
      if (r2) {
        r2.rotation.z = t * 0.22;
        r2.rotation.y = Math.sin(t * 0.35) * 0.3 + Math.PI / 8;
      }

      const r3 = ringsGroup.getObjectByName('ring3');
      if (r3) {
        r3.rotation.z = -t * 0.18;
        r3.rotation.x = Math.cos(t * 0.25) * 0.2 - Math.PI / 3;
      }

      const r4 = ringsGroup.getObjectByName('ring4');
      if (r4) r4.rotation.z = t * 0.11;
    }

    // Radar Sweep
    if (sweepGroup) {
      const radar = sweepGroup.getObjectByName('radarSweep');
      if (radar) radar.rotation.z = t * 1.2;
    }

    // Particle Matrix
    if (particlesGroup) {
      particlesGroup.rotation.y = t * 0.08;
      particlesGroup.rotation.x = Math.sin(t * 0.15) * 0.1;
    }

    // Core Resonant Breathing (Slow and elegant)
    if (coreGroup) {
      const ico = coreGroup.getObjectByName('icoMesh');
      if (ico) {
        ico.rotation.x = t * 0.5;
        ico.rotation.y = t * 0.7;
        const iScale = 1.0 + totalEnergy * 0.15;
        ico.scale.set(iScale, iScale, iScale);
      }

      const corona = coreGroup.getObjectByName('corona');
      if (corona) {
        const cScale = 1.0 + Math.sin(t * 1.8) * 0.05 + totalEnergy * 0.2;
        corona.scale.set(cScale, cScale, cScale);
        corona.rotation.y = t * 0.5;
        corona.rotation.z = t * 0.3;
      }

      const halo = coreGroup.getObjectByName('halo');
      if (halo) {
        const hScale = 1.0 + totalEnergy * 0.12;
        halo.scale.set(hScale, hScale, hScale);
      }

      const pLight = coreGroup.getObjectByName('pLight');
      if (pLight) {
        pLight.intensity = 3.6 + totalEnergy * 1.5;
      }
    }

    // ── Generate Smooth, Slow Fluid Harmonic Waves ──────────────────────────
    // Primary Inner Wave: Slow, smooth sinusoidal undulating swells
    if (innerGeometry && innerPositions) {
      const pos = innerPositions;
      const baseR = 5.6;
      const waveAmplitude = 0.15 + totalEnergy * 0.55;

      for (let i = 0; i <= WAVE_SEGMENTS; i++) {
        const theta = (i / WAVE_SEGMENTS) * Math.PI * 2;

        const h1 = Math.sin(theta * 6 - wavePhase * 1.5);
        const h2 = Math.sin(theta * 10 + wavePhase * 1.2) * 0.35;
        const fluidWave = (h1 + h2) / 1.35;

        const r = baseR + fluidWave * waveAmplitude;
        pos[i * 3] = Math.cos(theta) * r;
        pos[i * 3 + 1] = Math.sin(theta) * r;
        pos[i * 3 + 2] = Math.sin(theta * 4 + wavePhase * 1.0) * 0.18 * totalEnergy;
      }
      innerGeometry.attributes.position.needsUpdate = true;
    }

    // Secondary Outer Wave: Smooth gentle ripple
    if (outerGeometry && outerPositions) {
      const pos = outerPositions;
      const baseR = 8.2;
      const waveAmplitude = 0.1 + totalEnergy * 0.38;

      for (let i = 0; i <= WAVE_SEGMENTS; i++) {
        const theta = (i / WAVE_SEGMENTS) * Math.PI * 2;

        const h1 = Math.sin(theta * 8 + wavePhase * 1.1);
        const h2 = Math.sin(theta * 12 - wavePhase * 0.9) * 0.25;
        const fluidWave = (h1 + h2) / 1.25;

        const r = baseR + fluidWave * waveAmplitude;
        pos[i * 3] = Math.cos(theta) * r;
        pos[i * 3 + 1] = Math.sin(theta) * r;
        pos[i * 3 + 2] = Math.cos(theta * 6 - wavePhase * 0.8) * 0.12 * totalEnergy;
      }
      outerGeometry.attributes.position.needsUpdate = true;
    }

    renderer.render(scene, camera);
  }

  // Public API to interface with app.js (Gentle, slow pulses)
  window.jarvisHolo = {
    startSpeaking() {
      isSpeaking = true;
      targetWaveEnergy = Math.max(targetWaveEnergy, 0.45);
    },

    stopSpeaking() {
      isSpeaking = false;
    },

    // Gentle Word Pulse: Smoothly swells waves at a calm, majestic pace
    pulseWord(amount = 0.3) {
      targetWaveEnergy = Math.min(1.0, targetWaveEnergy + amount * 0.3);
    },

    pulse(amount = 0.3) {
      targetWaveEnergy = Math.min(1.0, targetWaveEnergy + amount * 0.25);
    },

    vibrate(amount = 0.3) {
      targetWaveEnergy = Math.min(1.0, targetWaveEnergy + amount * 0.3);
    },

    setView(viewName) {
      if (viewName === 'front') {
        targetRotationX = 0;
        targetRotationY = 0;
        targetRotationZ = 0;
      } else if (viewName === 'top') {
        targetRotationX = Math.PI / 2;
        targetRotationY = 0;
        targetRotationZ = 0;
      } else if (viewName === 'bottom') {
        targetRotationX = -Math.PI / 2;
        targetRotationY = 0;
        targetRotationZ = 0;
      } else if (viewName === 'side') {
        targetRotationX = 0;
        targetRotationY = Math.PI / 2;
        targetRotationZ = 0;
      } else if (viewName === 'iso') {
        targetRotationX = 0.55;
        targetRotationY = 0.75;
        targetRotationZ = 0.15;
      }
      momentumX = 0;
      momentumY = 0;
    },

    toggleAutoSpin() {
      autoOrbit = !autoOrbit;
      return autoOrbit;
    },

    isAutoSpinning() {
      return autoOrbit;
    },

    setZoom(level) {
      targetCameraZ = Math.max(0.015, Math.min(12000, level));
    },

    resetView() {
      targetRotationX = 0.12;
      targetRotationY = 0.25;
      targetRotationZ = 0;
      targetCameraZ = 48;
      momentumX = 0;
      momentumY = 0;
      autoOrbit = true;
    },
  };

  // Auto-init when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
