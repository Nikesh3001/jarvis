/**
 * FRIDAY 3D Holographic Spatial Engine
 * Powered by Three.js
 * Featuring Iron Man Mark 85 Interactive 3D Hologram
 */

(function () {
  'use strict';

  if (typeof THREE === 'undefined') {
    console.error('Three.js library is not loaded');
    return;
  }

  // State
  let scene, camera, renderer, raycaster, mouse;
  let canvasContainer, canvas;
  let currentMode = 'ironman'; // 'ironman' | 'reactor' | 'globe'
  let isStarkMode = true;
  let autoRotate = false; // By default let user inspect Iron Man or look at him
  let rotateSpeed = 0.005;
  let explodeAmount = 0.0;
  let isSpeaking = false;
  let audioPulse = 0;
  let animationFrameId = null;

  // Groups
  let mainGroup = null;
  let ironmanGroup = null;
  let headGroup = null;
  let faceplateGroup = null;
  let chestGroup = null;
  let reactorGroup = null;
  let globeGroup = null;
  let particleSystem = null;
  let particleGeo = null;
  let hudReticle = null;
  let chestReactorCore = null;
  let eyeLights = [];

  // Interactive Hotspots
  const hotspots = [];
  let hoveredHotspot = null;

  // Camera targets for smooth lerp
  const targetCamPos = new THREE.Vector3(0, 4, 60);
  const targetLookAt = new THREE.Vector3(0, 6, 0);
  const currentLookAt = new THREE.Vector3(0, 6, 0);

  // Palette definitions
  const PALETTES = {
    stark: {
      crimson: 0x9e0018,
      crimsonDark: 0x6e0010,
      gold: 0xf59e0b,
      goldLight: 0xfde047,
      titanium: 0x334155,
      arcCyan: 0x00f0ff,
      arcWhite: 0xffffff,
      glow: 0x00f0ff,
      ambient: 0x1e3a5f,
    },
    stealth: {
      crimson: 0x1e293b,
      crimsonDark: 0x0f172a,
      gold: 0x64748b,
      goldLight: 0x94a3b8,
      titanium: 0x1e293b,
      arcCyan: 0x38bdf8,
      arcWhite: 0xffffff,
      glow: 0x38bdf8,
      ambient: 0x0f172a,
    },
  };

  function getPalette() {
    return isStarkMode ? PALETTES.stark : PALETTES.stealth;
  }

  // Initialize Scene
  function init() {
    canvasContainer = document.getElementById('threejs-container');
    canvas = document.getElementById('threejs-canvas');
    if (!canvasContainer || !canvas) return;

    const width = canvasContainer.clientWidth || window.innerWidth;
    const height = canvasContainer.clientHeight || window.innerHeight;

    // Scene & Depth Fog
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x060b14, 0.0035);

    // Camera
    camera = new THREE.PerspectiveCamera(46, width / height, 0.1, 1000);
    camera.position.set(0, 5, 60);
    targetCamPos.copy(camera.position);

    // Renderer
    renderer = new THREE.WebGLRenderer({
      canvas: canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.35;

    // WebGL Context Lost handling
    canvas.addEventListener('webglcontextlost', (e) => {
      e.preventDefault();
      console.warn('WebGL context lost. Pausing 3D spatial loop.');
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
    });
    canvas.addEventListener('webglcontextrestored', () => {
      console.info('WebGL context restored. Rebuilding 3D scene.');
      init();
    });

    // Raycaster & Mouse
    raycaster = new THREE.Raycaster();
    mouse = new THREE.Vector2(0, 0);

    // Lighting
    setupLighting();

    // Main rotating group
    mainGroup = new THREE.Group();
    scene.add(mainGroup);

    // Build modules
    buildBackgroundGrid();
    buildParticleField();
    buildIronMan();
    buildArcReactor();
    buildGlobalGlobe();

    // Set initial mode to Iron Man!
    setMode('ironman');

    // Controls & Events
    setupOrbitInteraction();
    window.addEventListener('resize', onWindowResize);

    // Start render loop
    animate(0);
  }

  function setupLighting() {
    const ambient = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambient);

    // Front Key Light (Warm metallic highlight)
    const keyLight = new THREE.DirectionalLight(0xfffaed, 2.0);
    keyLight.position.set(30, 45, 50);
    scene.add(keyLight);

    // Cool Rim Light (Sharp blue edge separation)
    const rimLight = new THREE.DirectionalLight(0x00f0ff, 2.2);
    rimLight.position.set(-40, 20, -35);
    scene.add(rimLight);

    // Bottom Up-light (Gives cinematic specular sheen on armor plates)
    const bounceLight = new THREE.DirectionalLight(0xd97706, 0.8);
    bounceLight.position.set(0, -30, 20);
    scene.add(bounceLight);

    // Chest RT Arc Glow Point Light
    const arcLight = new THREE.PointLight(0x00f0ff, 4.5, 40);
    arcLight.position.set(0, 3, 10);
    arcLight.name = 'arcPointLight';
    scene.add(arcLight);
  }

  // ── Background Space Grid & Ambient Particles ───────────────────────────

  function buildBackgroundGrid() {
    const size = 180;
    const divisions = 24;
    const grid = new THREE.GridHelper(size, divisions, 0x1e3a5f, 0x071524);
    grid.position.y = -25;
    scene.add(grid);

    // Outer circular boundary ring
    const ringGeo = new THREE.RingGeometry(65, 66, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.2,
    });
    const horizonRing = new THREE.Mesh(ringGeo, ringMat);
    horizonRing.rotation.x = Math.PI / 2;
    horizonRing.position.y = -24.8;
    scene.add(horizonRing);
  }

  function buildParticleField() {
    const pCount = 900;
    particleGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(pCount * 3);

    for (let i = 0; i < pCount; i++) {
      const radius = 25 + Math.random() * 40;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = radius * Math.cos(phi);
    }

    particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const pMat = new THREE.PointsMaterial({
      color: 0x00f0ff,
      size: 1.2,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
    });

    particleSystem = new THREE.Points(particleGeo, pMat);
    scene.add(particleSystem);
  }

  // ── Masterpiece: 3D Iron Man Mark 85 Armor & Helmet ─────────────────────

  function buildIronMan() {
    ironmanGroup = new THREE.Group();
    ironmanGroup.name = 'ironmanGroup';
    ironmanGroup.position.set(0, -5, 0);

    const p = getPalette();

    // Metallic Materials
    const matCrimson = new THREE.MeshStandardMaterial({
      color: p.crimson,
      metalness: 0.88,
      roughness: 0.22,
    });

    const matCrimsonDark = new THREE.MeshStandardMaterial({
      color: p.crimsonDark,
      metalness: 0.85,
      roughness: 0.3,
    });

    const matGold = new THREE.MeshStandardMaterial({
      color: p.gold,
      metalness: 0.92,
      roughness: 0.26,
    });

    const matTitanium = new THREE.MeshStandardMaterial({
      color: p.titanium,
      metalness: 0.95,
      roughness: 0.18,
    });

    const matArcGlow = new THREE.MeshBasicMaterial({
      color: p.arcCyan,
    });

    const matEyeGlow = new THREE.MeshBasicMaterial({
      color: 0xffffff,
    });

    // ─────────────────────────────────────────────────────────────────────────
    // 1. CHEST & TORSO ASSEMBLY
    // ─────────────────────────────────────────────────────────────────────────
    chestGroup = new THREE.Group();
    chestGroup.name = 'ironmanChest';

    // Main Torso Chassis (Inner Frame)
    const torsoChassisGeo = new THREE.CylinderGeometry(8.5, 7.0, 16, 16);
    const torsoChassis = new THREE.Mesh(torsoChassisGeo, matTitanium);
    torsoChassis.position.y = 5;
    chestGroup.add(torsoChassis);

    // Left and Right Pectoral Armor Plates
    const pecGeo = new THREE.BoxGeometry(6.5, 7.5, 2.8);

    const leftPec = new THREE.Mesh(pecGeo, matCrimson.clone());
    leftPec.position.set(-4.5, 8.5, 6.2);
    leftPec.rotation.y = 0.18;
    leftPec.rotation.z = -0.05;
    leftPec.userData = { normal: new THREE.Vector3(-0.9, 0.2, 1).normalize() };
    chestGroup.add(leftPec);

    const rightPec = new THREE.Mesh(pecGeo, matCrimson.clone());
    rightPec.position.set(4.5, 8.5, 6.2);
    rightPec.rotation.y = -0.18;
    rightPec.rotation.z = 0.05;
    rightPec.userData = { normal: new THREE.Vector3(0.9, 0.2, 1).normalize() };
    chestGroup.add(rightPec);

    // Clavicle & Trapezius Gold Armor Bars
    const clavicleGeo = new THREE.BoxGeometry(7, 2, 2.5);

    const leftClavicle = new THREE.Mesh(clavicleGeo, matGold);
    leftClavicle.position.set(-6, 13, 4.5);
    leftClavicle.rotation.z = 0.15;
    chestGroup.add(leftClavicle);

    const rightClavicle = new THREE.Mesh(clavicleGeo, matGold);
    rightClavicle.position.set(6, 13, 4.5);
    rightClavicle.rotation.z = -0.15;
    chestGroup.add(rightClavicle);

    // Central Triangular RT Arc Reactor Core Housing
    const arcHousingGeo = new THREE.CylinderGeometry(3.6, 3.6, 2.2, 6);
    const arcHousing = new THREE.Mesh(arcHousingGeo, matTitanium);
    arcHousing.rotation.x = Math.PI / 2;
    arcHousing.position.set(0, 8.5, 7.2);
    chestGroup.add(arcHousing);

    // Glowing Triangular Arc Lens
    const arcLensGeo = new THREE.CircleGeometry(2.6, 3);
    const arcLens = new THREE.Mesh(arcLensGeo, matArcGlow);
    arcLens.rotation.z = Math.PI; // Inverted triangle shape (classic Mark 85)
    arcLens.position.set(0, 8.5, 8.4);
    arcLens.name = 'arcLens';
    chestReactorCore = arcLens;
    chestGroup.add(arcLens);

    // Arc Core Pulsing Outer Ring
    const arcRingGeo = new THREE.RingGeometry(2.8, 3.3, 32);
    const arcRingMat = new THREE.MeshBasicMaterial({
      color: p.arcCyan,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.8,
    });
    const arcRing = new THREE.Mesh(arcRingGeo, arcRingMat);
    arcRing.position.set(0, 8.5, 8.42);
    arcRing.name = 'arcRing';
    chestGroup.add(arcRing);

    // Segmented Abdominal Armor Plates (Interlocking Crimson & Gold)
    for (let i = 0; i < 3; i++) {
      const abGeo = new THREE.BoxGeometry(8 - i * 1.2, 2.2, 2.2);
      const abPlate = new THREE.Mesh(abGeo, i % 2 === 0 ? matCrimsonDark : matGold);
      abPlate.position.set(0, 3.6 - i * 2.5, 5.8 - i * 0.4);
      abPlate.userData = { normal: new THREE.Vector3(0, -0.2, 1).normalize() };
      chestGroup.add(abPlate);
    }

    // Aerodynamic Shoulder Pauldrons (Deltoids)
    const pauldronGeo = new THREE.ConeGeometry(5.2, 6.5, 5);

    const leftPauldron = new THREE.Mesh(pauldronGeo, matCrimson);
    leftPauldron.position.set(-13.5, 12, 1.5);
    leftPauldron.rotation.z = 0.55;
    leftPauldron.rotation.y = 0.2;
    chestGroup.add(leftPauldron);

    const rightPauldron = new THREE.Mesh(pauldronGeo, matCrimson);
    rightPauldron.position.set(13.5, 12, 1.5);
    rightPauldron.rotation.z = -0.55;
    rightPauldron.rotation.y = -0.2;
    chestGroup.add(rightPauldron);

    // Gold Shoulder Trim Inlays
    const trimGeo = new THREE.BoxGeometry(4.5, 1.2, 4);
    const leftTrim = new THREE.Mesh(trimGeo, matGold);
    leftTrim.position.set(-13, 14.5, 1.5);
    leftTrim.rotation.z = 0.35;
    chestGroup.add(leftTrim);

    const rightTrim = new THREE.Mesh(trimGeo, matGold);
    rightTrim.position.set(13, 14.5, 1.5);
    rightTrim.rotation.z = -0.35;
    chestGroup.add(rightTrim);

    ironmanGroup.add(chestGroup);

    // ─────────────────────────────────────────────────────────────────────────
    // 2. NECK & CERVICAL PISTONS
    // ─────────────────────────────────────────────────────────────────────────
    const neckGroup = new THREE.Group();
    neckGroup.position.set(0, 14, 1);

    const neckPillar = new THREE.Mesh(
      new THREE.CylinderGeometry(3.5, 4.2, 4.5, 16),
      matTitanium
    );
    neckGroup.add(neckPillar);

    // Hydraulic side pistons
    const pistonGeo = new THREE.CylinderGeometry(0.5, 0.5, 4, 8);
    const leftPiston = new THREE.Mesh(pistonGeo, matTitanium);
    leftPiston.position.set(-3.2, 0, 0.8);
    leftPiston.rotation.z = 0.15;
    neckGroup.add(leftPiston);

    const rightPiston = new THREE.Mesh(pistonGeo, matTitanium);
    rightPiston.position.set(3.2, 0, 0.8);
    rightPiston.rotation.z = -0.15;
    neckGroup.add(rightPiston);

    ironmanGroup.add(neckGroup);

    // ─────────────────────────────────────────────────────────────────────────
    // 3. THE ICONIC IRON MAN HELMET & FACEPLATE
    // ─────────────────────────────────────────────────────────────────────────
    headGroup = new THREE.Group();
    headGroup.name = 'ironmanHead';
    headGroup.position.set(0, 18, 1);

    // Cranium Dome (Crimson metallic curved skull shell)
    const craniumGeo = new THREE.SphereGeometry(6.4, 24, 24, 0, Math.PI * 2, 0, Math.PI * 0.7);
    const cranium = new THREE.Mesh(craniumGeo, matCrimson);
    cranium.position.set(0, 1.2, -0.6);
    headGroup.add(cranium);

    // Back of Helmet Neck Guard
    const backGuardGeo = new THREE.CylinderGeometry(5.8, 5.2, 5, 16, 1, false, 0, Math.PI);
    const backGuard = new THREE.Mesh(backGuardGeo, matCrimson);
    backGuard.position.set(0, -1.8, -1.8);
    backGuard.rotation.y = Math.PI;
    headGroup.add(backGuard);

    // Ear Circular Repulsor / Audio Transducers
    const earGeo = new THREE.CylinderGeometry(2.0, 2.0, 0.8, 24);

    const leftEar = new THREE.Mesh(earGeo, matGold);
    leftEar.rotation.z = Math.PI / 2;
    leftEar.position.set(-6.2, 0.5, 0);
    headGroup.add(leftEar);

    const rightEar = new THREE.Mesh(earGeo, matGold);
    rightEar.rotation.z = Math.PI / 2;
    rightEar.position.set(6.2, 0.5, 0);
    headGroup.add(rightEar);

    // ── The Sculpted Faceplate Group (Lifts up on Explode) ──
    faceplateGroup = new THREE.Group();
    faceplateGroup.name = 'faceplateGroup';

    // Faceplate Forehead Brow (Gold)
    const browGeo = new THREE.BoxGeometry(6.6, 2.4, 3.2);
    const brow = new THREE.Mesh(browGeo, matGold);
    brow.position.set(0, 2.6, 4.4);
    brow.rotation.x = -0.25;
    faceplateGroup.add(brow);

    // Cheekbone Left & Right Angular Bevels (Gold)
    const cheekGeo = new THREE.BoxGeometry(2.5, 4.8, 3.0);

    const leftCheek = new THREE.Mesh(cheekGeo, matGold);
    leftCheek.position.set(-3.2, -0.2, 4.2);
    leftCheek.rotation.y = -0.35;
    leftCheek.rotation.z = 0.1;
    faceplateGroup.add(leftCheek);

    const rightCheek = new THREE.Mesh(cheekGeo, matGold);
    rightCheek.position.set(3.2, -0.2, 4.2);
    rightCheek.rotation.y = 0.35;
    rightCheek.rotation.z = -0.1;
    faceplateGroup.add(rightCheek);

    // Tapered Jaw / Mandible Chin Plate (Gold)
    const jawGeo = new THREE.BoxGeometry(4.4, 2.6, 3.4);
    const jaw = new THREE.Mesh(jawGeo, matGold);
    jaw.position.set(0, -3.2, 3.8);
    jaw.rotation.x = 0.25;
    faceplateGroup.add(jaw);

    // Center Nose/Mouth Bridge
    const bridgeGeo = new THREE.BoxGeometry(2.4, 2.8, 1.8);
    const bridge = new THREE.Mesh(bridgeGeo, matGold);
    bridge.position.set(0, -0.8, 5.2);
    faceplateGroup.add(bridge);

    // ── Glowing Eye Lenses (The Signature Iron Man Slits) ──
    const eyeGeo = new THREE.BoxGeometry(2.1, 0.45, 0.8);

    const leftEye = new THREE.Mesh(eyeGeo, matEyeGlow);
    leftEye.position.set(-2.0, 1.2, 5.6);
    leftEye.rotation.z = -0.22; // Signature menacing eye tilt
    leftEye.name = 'leftEye';
    faceplateGroup.add(leftEye);

    const rightEye = new THREE.Mesh(eyeGeo, matEyeGlow);
    rightEye.position.set(2.0, 1.2, 5.6);
    rightEye.rotation.z = 0.22;
    rightEye.name = 'rightEye';
    faceplateGroup.add(rightEye);

    // Point lights for the glowing eyes
    const leftEyeLight = new THREE.PointLight(0x00f0ff, 2.5, 12);
    leftEyeLight.position.set(-2.0, 1.2, 7.0);
    faceplateGroup.add(leftEyeLight);
    eyeLights.push(leftEyeLight);

    const rightEyeLight = new THREE.PointLight(0x00f0ff, 2.5, 12);
    rightEyeLight.position.set(2.0, 1.2, 7.0);
    faceplateGroup.add(rightEyeLight);
    eyeLights.push(rightEyeLight);

    headGroup.add(faceplateGroup);

    // ─────────────────────────────────────────────────────────────────────────
    // 4. FLOATING 3D HOLOGRAPHIC HUD TARGETING RETICLE (FRIDAY AR Overlay)
    // ─────────────────────────────────────────────────────────────────────────
    hudReticle = new THREE.Group();
    hudReticle.name = 'hudReticle';
    hudReticle.position.set(0, 1.2, 12);

    // Outer Target Circle
    const reticleGeo = new THREE.RingGeometry(5.5, 5.8, 36);
    const reticleMat = new THREE.MeshBasicMaterial({
      color: p.arcCyan,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.7,
    });
    const reticleRing = new THREE.Mesh(reticleGeo, reticleMat);
    hudReticle.add(reticleRing);

    // Crosshair Corner Brackets
    for (let c = 0; c < 4; c++) {
      const angle = (c * Math.PI) / 2 + Math.PI / 4;
      const bracketGeo = new THREE.RingGeometry(4.2, 4.5, 8, 1, angle - 0.25, 0.5);
      const bracket = new THREE.Mesh(bracketGeo, reticleMat);
      hudReticle.add(bracket);
    }

    headGroup.add(hudReticle);
    ironmanGroup.add(headGroup);

    // ─────────────────────────────────────────────────────────────────────────
    // 5. INTERACTIVE 3D SENSOR HOTSPOTS
    // ─────────────────────────────────────────────────────────────────────────
    createHotspot('Optical HUD & Target Matrix', '120 FPS Neural Target Lock · Threat Detection Active', 0, 19.5, 9, ironmanGroup);
    createHotspot('RT Arc Reactor Core', 'Mark 85 Clean Energy · Output: 10.4 GW · Zero Degradation', 0, 4, 10, ironmanGroup);
    createHotspot('Gold-Titanium Faceplate', 'Nanoparticle Matrix · Kinetic Deflection 99.8%', 4.5, 18, 6, ironmanGroup);
    createHotspot('Vibro-Stabilized Pauldron', 'Kinetic Absorption Damper · Ballistic Class IV', -13.5, 8, 3, ironmanGroup);

    mainGroup.add(ironmanGroup);
  }

  // ── Mode 2: Arc Reactor Close-Up ─────────────────────────────────────────

  function buildArcReactor() {
    reactorGroup = new THREE.Group();
    reactorGroup.name = 'reactorGroup';
    reactorGroup.visible = false;

    const p = getPalette();

    // Central Plasma Core Sphere
    const coreGeo = new THREE.SphereGeometry(6.5, 32, 32);
    const coreMat = new THREE.MeshStandardMaterial({
      color: 0x38bdf8,
      emissive: 0x00f0ff,
      emissiveIntensity: 1.8,
      roughness: 0.2,
      metalness: 0.8,
    });
    const core = new THREE.Mesh(coreGeo, coreMat);
    core.name = 'plasmaCore';
    reactorGroup.add(core);

    // Primary Torus Confinement Coil
    const torusGeo = new THREE.TorusGeometry(14, 1.8, 16, 64);
    const torusMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.3,
      metalness: 0.9,
    });
    const torus = new THREE.Mesh(torusGeo, torusMat);
    reactorGroup.add(torus);

    // Ten Radial Copper Wound Segments
    for (let i = 0; i < 10; i++) {
      const angle = (i / 10) * Math.PI * 2;
      const segGeo = new THREE.BoxGeometry(2.4, 5.5, 3.2);
      const segMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.95 });
      const segment = new THREE.Mesh(segGeo, segMat);
      segment.position.set(Math.cos(angle) * 14, Math.sin(angle) * 14, 0);
      segment.rotation.z = angle + Math.PI / 2;
      reactorGroup.add(segment);
    }

    // Outer Gimbals
    const gimbal1Geo = new THREE.TorusGeometry(20, 0.6, 12, 64);
    const gimbal1Mat = new THREE.MeshBasicMaterial({ color: p.arcCyan, wireframe: true, transparent: true, opacity: 0.6 });
    const gimbal1 = new THREE.Mesh(gimbal1Geo, gimbal1Mat);
    gimbal1.name = 'gimbal1';
    reactorGroup.add(gimbal1);

    const gimbal2Geo = new THREE.TorusGeometry(24, 0.5, 12, 64);
    const gimbal2Mat = new THREE.MeshBasicMaterial({ color: p.gold, wireframe: true, transparent: true, opacity: 0.5 });
    const gimbal2 = new THREE.Mesh(gimbal2Geo, gimbal2Mat);
    gimbal2.name = 'gimbal2';
    gimbal2.rotation.x = Math.PI / 4;
    reactorGroup.add(gimbal2);

    createHotspot('Plasma Confinement Field', 'Magnetic Flux: 14.2 Tesla · Superconducting', 0, 0, 8, reactorGroup);
    mainGroup.add(reactorGroup);
  }

  // ── Mode 3: Global Orbital Telemetry Globe ───────────────────────────────

  function buildGlobalGlobe() {
    globeGroup = new THREE.Group();
    globeGroup.name = 'globeGroup';
    globeGroup.visible = false;

    const p = getPalette();

    const globeGeo = new THREE.SphereGeometry(18, 32, 32);
    const globeMat = new THREE.MeshBasicMaterial({
      color: p.arcCyan,
      wireframe: true,
      transparent: true,
      opacity: 0.4,
    });
    const globeMesh = new THREE.Mesh(globeGeo, globeMat);
    globeGroup.add(globeMesh);

    // Inner dark sphere to occlude back
    const innerGlobe = new THREE.Mesh(
      new THREE.SphereGeometry(17.6, 32, 32),
      new THREE.MeshBasicMaterial({ color: 0x050d18 })
    );
    globeGroup.add(innerGlobe);

    // Key Global Beacons
    const locations = [
      { name: 'Stark Tower (New York)', lat: 40.71, lon: -74.0, desc: 'Primary Intelligence Hub · 10 Gbps Uplink' },
      { name: 'Malibu Lab (California)', lat: 34.02, lon: -118.77, desc: 'R&D Fabrication · Nanotech Foundry' },
      { name: 'Tokyo Research Center', lat: 35.67, lon: 139.65, desc: 'Quantum Neural Node · Latency 14ms' },
      { name: 'Zurich Vault', lat: 47.37, lon: 8.54, desc: 'Encrypted Cold Storage · Zero-Knowledge' },
    ];

    locations.forEach((loc) => {
      const phi = (90 - loc.lat) * (Math.PI / 180);
      const theta = (loc.lon + 180) * (Math.PI / 180);
      const radius = 18.2;

      const x = -(radius * Math.sin(phi) * Math.cos(theta));
      const z = radius * Math.sin(phi) * Math.sin(theta);
      const y = radius * Math.cos(phi);

      const pinGeo = new THREE.CylinderGeometry(0.3, 0.1, 3.5, 8);
      const pinMat = new THREE.MeshBasicMaterial({ color: 0xff3b30 });
      const pin = new THREE.Mesh(pinGeo, pinMat);
      pin.position.set(x, y, z);
      pin.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(x, y, z).normalize());
      globeGroup.add(pin);

      createHotspot(loc.name, loc.desc, x * 1.05, y * 1.05, z * 1.05, globeGroup);
    });

    mainGroup.add(globeGroup);
  }

  // ── Hotspot Helper ───────────────────────────────────────────────────────

  function createHotspot(title, description, x, y, z, parentGroup) {
    const group = new THREE.Group();
    group.position.set(x, y, z);

    const ringGeo = new THREE.RingGeometry(0.8, 1.1, 16);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.85,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    group.add(ring);

    const dotGeo = new THREE.CircleGeometry(0.4, 12);
    const dotMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      side: THREE.DoubleSide,
    });
    const dot = new THREE.Mesh(dotGeo, dotMat);
    group.add(dot);

    group.userData = {
      isHotspot: true,
      title: title,
      description: description,
    };

    parentGroup.add(group);
    hotspots.push(group);
  }

  // ── Orbit & Interaction Controls ─────────────────────────────────────────

  function setupOrbitInteraction() {
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;

    canvas.addEventListener('mousedown', (e) => {
      isDragging = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    });

    window.addEventListener('mouseup', () => {
      isDragging = false;
    });

    window.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      if (isDragging && mainGroup) {
        const deltaX = e.clientX - prevMouseX;
        const deltaY = e.clientY - prevMouseY;
        prevMouseX = e.clientX;
        prevMouseY = e.clientY;

        mainGroup.rotation.y += deltaX * 0.005;
        mainGroup.rotation.x = Math.max(-0.5, Math.min(0.5, mainGroup.rotation.x + deltaY * 0.005));
      }
    });

    // Touch support
    canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        isDragging = true;
        prevMouseX = e.touches[0].clientX;
        prevMouseY = e.touches[0].clientY;
      }
    }, { passive: true });

    window.addEventListener('touchend', () => {
      isDragging = false;
    });

    window.addEventListener('touchmove', (e) => {
      if (isDragging && e.touches.length === 1 && mainGroup) {
        const deltaX = e.touches[0].clientX - prevMouseX;
        const deltaY = e.touches[0].clientY - prevMouseY;
        prevMouseX = e.touches[0].clientX;
        prevMouseY = e.touches[0].clientY;

        mainGroup.rotation.y += deltaX * 0.006;
      }
    }, { passive: true });

    // Zoom on wheel
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY * 0.04;
      targetCamPos.z = Math.max(30, Math.min(110, targetCamPos.z + zoomFactor));
    }, { passive: false });

    // Click hotspot to show diagnostic inspect card
    canvas.addEventListener('click', () => {
      if (hoveredHotspot) {
        showHotspotCard(hoveredHotspot.userData.title, hoveredHotspot.userData.description);
        targetLookAt.copy(hoveredHotspot.position);
      }
    });
  }

  function showHotspotCard(title, description) {
    const card = document.getElementById('hotspot-inspect-card');
    const titleEl = document.getElementById('hotspot-title');
    const descEl = document.getElementById('hotspot-desc');
    if (!card || !titleEl || !descEl) return;

    titleEl.textContent = title;
    descEl.textContent = description;
    card.classList.add('visible');

    clearTimeout(card._timer);
    card._timer = setTimeout(() => {
      card.classList.remove('visible');
    }, 6000);
  }

  // ── Public API Methods ───────────────────────────────────────────────────

  function setMode(mode) {
    currentMode = mode;
    if (ironmanGroup) ironmanGroup.visible = mode === 'ironman';
    if (reactorGroup) reactorGroup.visible = mode === 'reactor';
    if (globeGroup) globeGroup.visible = mode === 'globe';

    if (mode === 'ironman') {
      targetCamPos.set(0, 5, 58);
      targetLookAt.set(0, 6, 0);
    } else if (mode === 'reactor') {
      targetCamPos.set(0, 0, 75);
      targetLookAt.set(0, 0, 0);
    } else if (mode === 'globe') {
      targetCamPos.set(0, 10, 85);
      targetLookAt.set(0, 0, 0);
    }

    document.querySelectorAll('.mode-3d-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    const explodeSlider = document.getElementById('explodeSliderContainer');
    if (explodeSlider) {
      explodeSlider.style.display = mode === 'ironman' ? 'flex' : 'none';
    }
  }

  function setCameraPreset(preset) {
    if (preset === 'front') {
      targetCamPos.set(0, 5, 58);
      if (mainGroup) {
        mainGroup.rotation.x = 0;
        mainGroup.rotation.y = 0;
      }
    } else if (preset === 'iso') {
      targetCamPos.set(35, 25, 52);
    } else if (preset === 'top') {
      targetCamPos.set(0, 65, 10);
      if (mainGroup) {
        mainGroup.rotation.x = 0;
      }
    } else if (preset === 'orbit') {
      autoRotate = !autoRotate;
    }
    targetLookAt.set(0, 6, 0);
  }

  function setStarkTheme(enabled) {
    isStarkMode = enabled;
  }

  function setExplodeAmount(amount) {
    explodeAmount = amount;

    // Faceplate lifts up and forward revealing the interior HUD
    if (faceplateGroup) {
      faceplateGroup.position.z = amount * 8;
      faceplateGroup.position.y = amount * 7;
      faceplateGroup.rotation.x = -amount * 0.75;
    }

    // Chest plates slide laterally
    if (chestGroup) {
      chestGroup.children.forEach((mesh) => {
        const norm = mesh.userData?.normal;
        if (norm) {
          mesh.position.x = mesh.position.x + norm.x * (amount * 12 - (mesh.userData._lastExplode || 0));
          mesh.position.y = mesh.position.y + norm.y * (amount * 12 - (mesh.userData._lastExplode || 0));
          mesh.position.z = mesh.position.z + norm.z * (amount * 12 - (mesh.userData._lastExplode || 0));
          mesh.userData._lastExplode = amount * 12;
        }
      });
    }
  }

  function setAudioReactive(active, intensity) {
    isSpeaking = active;
    audioPulse = intensity || (active ? 1.0 : 0);
  }

  // ── Render Loop ──────────────────────────────────────────────────────────

  function animate(time) {
    animationFrameId = requestAnimationFrame(animate);

    const t = time * 0.001;

    // Smooth camera lerp
    camera.position.lerp(targetCamPos, 0.05);
    currentLookAt.lerp(targetLookAt, 0.05);
    camera.lookAt(currentLookAt);

    // Audio reactivity decay / pulsation
    if (isSpeaking) {
      audioPulse = 0.5 + Math.sin(t * 14) * 0.5;
    } else {
      audioPulse = Math.max(0, audioPulse - 0.02);
    }

    // Auto-rotate main scene if enabled
    if (autoRotate && mainGroup) {
      mainGroup.rotation.y += rotateSpeed;
    }

    // ── Animate Iron Man ──
    if (ironmanGroup && ironmanGroup.visible) {
      // 1. Interactive Head Mouse Tracking!
      if (headGroup) {
        const targetHeadRotY = mouse.x * 0.45;
        const targetHeadRotX = -mouse.y * 0.25;
        headGroup.rotation.y += (targetHeadRotY - headGroup.rotation.y) * 0.06;
        headGroup.rotation.x += (targetHeadRotX - headGroup.rotation.x) * 0.06;
      }

      // 2. Subtle Idling Chest Breathing
      const breath = Math.sin(t * 2) * 0.02;
      ironmanGroup.position.y = -5 + breath * 3;

      // 3. RT Arc Reactor & Eye Emissive Pulse
      if (chestReactorCore) {
        const arcPulse = 1.0 + Math.sin(t * 3.5) * 0.15 + audioPulse * 0.6;
        chestReactorCore.scale.set(arcPulse, arcPulse, 1);
      }

      // 4. Floating Holographic HUD Crosshairs
      if (hudReticle) {
        hudReticle.rotation.z = t * 0.4;
      }

      // 5. Eye Lights Pulse
      eyeLights.forEach((light) => {
        light.intensity = 2.5 + audioPulse * 3.5;
      });
    }

    // Animate Module 2: Reactor Core
    if (reactorGroup && reactorGroup.visible) {
      const core = reactorGroup.getObjectByName('plasmaCore');
      if (core) {
        const pulse = 1.0 + Math.sin(t * 4) * 0.06 + audioPulse * 0.2;
        core.scale.set(pulse, pulse, pulse);
      }
      const g1 = reactorGroup.getObjectByName('gimbal1');
      if (g1) g1.rotation.z = -t * 0.4;
      const g2 = reactorGroup.getObjectByName('gimbal2');
      if (g2) g2.rotation.x = t * 0.5;
    }

    // Animate Module 3: Globe
    if (globeGroup && globeGroup.visible) {
      globeGroup.rotation.y += 0.003;
    }

    // Animate Ambient Particles
    if (particleGeo) {
      const positions = particleGeo.attributes.position.array;
      const count = positions.length / 3;
      for (let i = 0; i < count; i++) {
        positions[i * 3 + 1] += Math.sin(t + i) * 0.015;
      }
      particleGeo.attributes.position.needsUpdate = true;
    }

    // Orient Hotspots to face camera
    hotspots.forEach((h) => {
      h.quaternion.copy(camera.quaternion);
      const s = 1.0 + Math.sin(t * 3 + h.position.x) * 0.15;
      h.scale.set(s, s, s);
    });

    // Raycast hover detection on hotspots
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(hotspots, true);

    if (intersects.length > 0) {
      let root = intersects[0].object;
      while (root.parent && !root.userData?.isHotspot) {
        root = root.parent;
      }
      if (root.userData?.isHotspot) {
        hoveredHotspot = root;
        canvas.style.cursor = 'pointer';
        const tooltip = document.getElementById('hotspot-tooltip');
        if (tooltip) {
          tooltip.textContent = root.userData.title;
          tooltip.style.display = 'block';
          const p2d = toScreenPosition(root, camera, renderer);
          tooltip.style.left = p2d.x + 'px';
          tooltip.style.top = p2d.y - 30 + 'px';
        }
      }
    } else {
      hoveredHotspot = null;
      canvas.style.cursor = 'default';
      const tooltip = document.getElementById('hotspot-tooltip');
      if (tooltip) tooltip.style.display = 'none';
    }

    renderer.render(scene, camera);
  }

  function toScreenPosition(obj, cam, rend) {
    const vector = new THREE.Vector3();
    obj.getWorldPosition(vector);
    vector.project(cam);
    const widthHalf = rend.domElement.clientWidth / 2;
    const heightHalf = rend.domElement.clientHeight / 2;
    return {
      x: vector.x * widthHalf + widthHalf,
      y: -(vector.y * heightHalf) + heightHalf,
    };
  }

  function onWindowResize() {
    if (!camera || !renderer || !canvasContainer) return;
    const width = canvasContainer.clientWidth || window.innerWidth;
    const height = canvasContainer.clientHeight || window.innerHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }

  // Attach Public API to window.friday3D
  window.friday3D = {
    init: init,
    setMode: setMode,
    setCameraPreset: setCameraPreset,
    setStarkTheme: setStarkTheme,
    setExplodeAmount: setExplodeAmount,
    setAudioReactive: setAudioReactive,
    toggleAutoRotate: () => {
      autoRotate = !autoRotate;
      return autoRotate;
    },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
