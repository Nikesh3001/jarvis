/**
 * FRIDAY / I.R.O.N. M.A.N. 3D Spatial Holographic Engine
 * Full-Body Iron Man Mark III Interactive 3D Model
 * Powered by Three.js
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
  let autoRotate = false;
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
  let leftArmGroup = null;
  let rightArmGroup = null;
  let leftLegGroup = null;
  let rightLegGroup = null;
  let reactorGroup = null;
  let globeGroup = null;
  let particleSystem = null;
  let particleGeo = null;
  let hudReticle = null;
  let chestReactorCore = null;
  let eyeLights = [];
  let repulsorLights = [];

  // Interactive Hotspots
  const hotspots = [];
  let hoveredHotspot = null;

  // Camera targets: positioned to frame the full standing Iron Man Mark III
  const targetCamPos = new THREE.Vector3(0, 2, 54);
  const targetLookAt = new THREE.Vector3(0, 1, 0);
  const currentLookAt = new THREE.Vector3(0, 1, 0);

  // Mark III Metallic Color Palette
  const PALETTE = {
    crimson: 0xaa0e22,       // Iconic hot rod red metallic
    crimsonDark: 0x7a0816,   // Shadowed crimson
    gold: 0xf59e0b,          // Titanium gold thigh and faceplate
    goldLight: 0xfcd34d,     // Specular gold highlights
    titanium: 0x334155,      // Mechanical joints and frame
    silver: 0xe2e8f0,        // Chrome pistons & bolts
    arcCyan: 0x00f0ff,       // RT Arc Core and eye glow
    arcWhite: 0xffffff,
  };

  // Initialize Scene
  function init() {
    canvasContainer = document.getElementById('threejs-container');
    canvas = document.getElementById('threejs-canvas');
    if (!canvasContainer || !canvas) return;

    const width = canvasContainer.clientWidth || window.innerWidth;
    const height = canvasContainer.clientHeight || window.innerHeight;

    // Scene & Deep Atmospheric Fog
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x060b14, 0.0032);

    // Camera
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 2, 54);
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
    renderer.toneMappingExposure = 1.4;

    // WebGL Context Safety
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

    // Studio Lighting setup
    setupLighting();

    // Main rotating group
    mainGroup = new THREE.Group();
    scene.add(mainGroup);

    // Build modules
    buildBackgroundGrid();
    buildParticleField();
    buildFullBodyIronMan();
    buildArcReactor();
    buildGlobalGlobe();

    // Set initial mode to full body Iron Man
    setMode('ironman');

    // Controls & Events
    setupOrbitInteraction();
    window.addEventListener('resize', onWindowResize);

    // Start render loop
    animate(0);
  }

  function setupLighting() {
    const ambient = new THREE.AmbientLight(0xffffff, 0.75);
    scene.add(ambient);

    // Key Light (Warm metallic highlight on gold and red)
    const keyLight = new THREE.DirectionalLight(0xfff7ed, 2.2);
    keyLight.position.set(25, 40, 45);
    scene.add(keyLight);

    // Cool Rim Light (Sharp cyan edge contour)
    const rimLight = new THREE.DirectionalLight(0x00f0ff, 2.0);
    rimLight.position.set(-35, 20, -30);
    scene.add(rimLight);

    // Backstage Fill Light
    const fillLight = new THREE.DirectionalLight(0x93c5fd, 0.9);
    fillLight.position.set(0, -20, 30);
    scene.add(fillLight);

    // Chest RT Arc Core Point Light
    const arcLight = new THREE.PointLight(0x00f0ff, 4.0, 35);
    arcLight.position.set(0, 6, 8);
    arcLight.name = 'arcPointLight';
    scene.add(arcLight);
  }

  // ── Background Space Grid & Ambient Particles ───────────────────────────

  function buildBackgroundGrid() {
    const size = 180;
    const divisions = 24;
    const grid = new THREE.GridHelper(size, divisions, 0x1e3a5f, 0x081525);
    grid.position.y = -21;
    scene.add(grid);

    // Ground Holo Landing Pedestal (Iron Man stands on this illuminated ring)
    const pedestalGeo = new THREE.CylinderGeometry(14, 15, 1, 32);
    const pedestalMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      metalness: 0.9,
      roughness: 0.25,
    });
    const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
    pedestal.position.y = -20.5;
    scene.add(pedestal);

    // Glowing Neon Rim around Pedestal
    const rimGeo = new THREE.RingGeometry(13.8, 14.5, 48);
    const rimMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.7,
    });
    const rim = new THREE.Mesh(rimGeo, rimMat);
    rim.rotation.x = Math.PI / 2;
    rim.position.y = -19.95;
    scene.add(rim);
  }

  function buildParticleField() {
    const pCount = 800;
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
      opacity: 0.6,
      blending: THREE.AdditiveBlending,
    });

    particleSystem = new THREE.Points(particleGeo, pMat);
    scene.add(particleSystem);
  }

  // ── Masterpiece: Full-Body 3D Iron Man Mark III ──────────────────────────

  function buildFullBodyIronMan() {
    ironmanGroup = new THREE.Group();
    ironmanGroup.name = 'ironmanGroup';
    ironmanGroup.position.set(0, 0, 0);

    // Metallic Materials
    const matCrimson = new THREE.MeshStandardMaterial({
      color: PALETTE.crimson,
      metalness: 0.9,
      roughness: 0.22,
    });

    const matCrimsonDark = new THREE.MeshStandardMaterial({
      color: PALETTE.crimsonDark,
      metalness: 0.85,
      roughness: 0.28,
    });

    const matGold = new THREE.MeshStandardMaterial({
      color: PALETTE.gold,
      metalness: 0.92,
      roughness: 0.25,
    });

    const matTitanium = new THREE.MeshStandardMaterial({
      color: PALETTE.titanium,
      metalness: 0.95,
      roughness: 0.2,
    });

    const matArcGlow = new THREE.MeshBasicMaterial({
      color: 0xffffff,
    });

    const matEyeGlow = new THREE.MeshBasicMaterial({
      color: 0xffffff,
    });

    // ─────────────────────────────────────────────────────────────────────────
    // 1. CHEST & TORSO (Pectorals, RT Arc Core, Abdomen)
    // ─────────────────────────────────────────────────────────────────────────
    chestGroup = new THREE.Group();
    chestGroup.name = 'ironmanChest';

    // Main Torso Chassis (Crimson)
    const torsoChassisGeo = new THREE.CylinderGeometry(6.2, 5.0, 11, 16);
    const torsoChassis = new THREE.Mesh(torsoChassisGeo, matCrimson);
    torsoChassis.position.y = 4.5;
    chestGroup.add(torsoChassis);

    // Left and Right Pectoral Armor Plates
    const pecGeo = new THREE.BoxGeometry(4.8, 5.2, 2.2);

    const leftPec = new THREE.Mesh(pecGeo, matCrimson.clone());
    leftPec.position.set(-3.2, 6.8, 4.4);
    leftPec.rotation.y = 0.2;
    leftPec.userData = { normal: new THREE.Vector3(-0.9, 0.2, 1).normalize() };
    chestGroup.add(leftPec);

    const rightPec = new THREE.Mesh(pecGeo, matCrimson.clone());
    rightPec.position.set(3.2, 6.8, 4.4);
    rightPec.rotation.y = -0.2;
    rightPec.userData = { normal: new THREE.Vector3(0.9, 0.2, 1).normalize() };
    chestGroup.add(rightPec);

    // Clavicle & Collar Gold Ribs
    const clavicleGeo = new THREE.BoxGeometry(5.0, 1.4, 1.8);
    const leftClavicle = new THREE.Mesh(clavicleGeo, matGold);
    leftClavicle.position.set(-4.2, 10.0, 3.2);
    leftClavicle.rotation.z = 0.15;
    chestGroup.add(leftClavicle);

    const rightClavicle = new THREE.Mesh(clavicleGeo, matGold);
    rightClavicle.position.set(4.2, 10.0, 3.2);
    rightClavicle.rotation.z = -0.15;
    chestGroup.add(rightClavicle);

    // Central Circular RT Arc Reactor Housing (Mark III Circular Arc)
    const arcHousingGeo = new THREE.CylinderGeometry(2.4, 2.4, 1.6, 32);
    const arcHousing = new THREE.Mesh(arcHousingGeo, matTitanium);
    arcHousing.rotation.x = Math.PI / 2;
    arcHousing.position.set(0, 6.8, 5.0);
    chestGroup.add(arcHousing);

    // Circular Glowing Arc Core Lens
    const arcLensGeo = new THREE.CircleGeometry(1.9, 32);
    const arcLens = new THREE.Mesh(arcLensGeo, matArcGlow);
    arcLens.position.set(0, 6.8, 5.85);
    arcLens.name = 'arcLens';
    chestReactorCore = arcLens;
    chestGroup.add(arcLens);

    // Outer Concentric Cyan Arc Ring
    const arcRingGeo = new THREE.RingGeometry(1.9, 2.3, 32);
    const arcRingMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.85,
    });
    const arcRing = new THREE.Mesh(arcRingGeo, arcRingMat);
    arcRing.position.set(0, 6.8, 5.86);
    chestGroup.add(arcRing);

    // Segmented Abdominal Armor Plates (Interlocking Crimson & Gold)
    for (let i = 0; i < 3; i++) {
      const abGeo = new THREE.BoxGeometry(5.8 - i * 0.8, 1.6, 1.8);
      const abPlate = new THREE.Mesh(abGeo, i % 2 === 0 ? matCrimsonDark : matGold);
      abPlate.position.set(0, 3.2 - i * 1.8, 4.2 - i * 0.3);
      abPlate.userData = { normal: new THREE.Vector3(0, -0.2, 1).normalize() };
      chestGroup.add(abPlate);
    }

    ironmanGroup.add(chestGroup);

    // ─────────────────────────────────────────────────────────────────────────
    // 2. NECK & ARTICULATED CYLINDER
    // ─────────────────────────────────────────────────────────────────────────
    const neck = new THREE.Mesh(
      new THREE.CylinderGeometry(2.4, 3.0, 3.2, 16),
      matTitanium
    );
    neck.position.set(0, 10.8, 0.6);
    ironmanGroup.add(neck);

    // ─────────────────────────────────────────────────────────────────────────
    // 3. THE ICONIC MARK III HELMET & GOLD FACEPLATE
    // ─────────────────────────────────────────────────────────────────────────
    headGroup = new THREE.Group();
    headGroup.name = 'ironmanHead';
    headGroup.position.set(0, 13.8, 0.8);

    // Helmet Cranium Dome (Crimson Metallic)
    const craniumGeo = new THREE.SphereGeometry(4.6, 24, 24, 0, Math.PI * 2, 0, Math.PI * 0.72);
    const cranium = new THREE.Mesh(craniumGeo, matCrimson);
    cranium.position.set(0, 0.8, -0.4);
    headGroup.add(cranium);

    // Circular Ear Audio Transducers / Repulsors (Gold)
    const earGeo = new THREE.CylinderGeometry(1.5, 1.5, 0.6, 24);

    const leftEar = new THREE.Mesh(earGeo, matGold);
    leftEar.rotation.z = Math.PI / 2;
    leftEar.position.set(-4.5, 0.2, 0);
    headGroup.add(leftEar);

    const rightEar = new THREE.Mesh(earGeo, matGold);
    rightEar.rotation.z = Math.PI / 2;
    rightEar.position.set(4.5, 0.2, 0);
    headGroup.add(rightEar);

    // ── Gold Faceplate Group (Lifts up on Explode) ──
    faceplateGroup = new THREE.Group();
    faceplateGroup.name = 'faceplateGroup';

    // Faceplate Brow / Forehead (Gold)
    const browGeo = new THREE.BoxGeometry(4.8, 1.8, 2.4);
    const brow = new THREE.Mesh(browGeo, matGold);
    brow.position.set(0, 1.8, 3.2);
    brow.rotation.x = -0.25;
    faceplateGroup.add(brow);

    // Cheekbone Left & Right Angular Bevels (Gold)
    const cheekGeo = new THREE.BoxGeometry(1.8, 3.6, 2.2);

    const leftCheek = new THREE.Mesh(cheekGeo, matGold);
    leftCheek.position.set(-2.4, -0.2, 3.1);
    leftCheek.rotation.y = -0.35;
    faceplateGroup.add(leftCheek);

    const rightCheek = new THREE.Mesh(cheekGeo, matGold);
    rightCheek.position.set(2.4, -0.2, 3.1);
    rightCheek.rotation.y = 0.35;
    faceplateGroup.add(rightCheek);

    // Mandible / Chin Plate (Gold)
    const jawGeo = new THREE.BoxGeometry(3.2, 1.8, 2.4);
    const jaw = new THREE.Mesh(jawGeo, matGold);
    jaw.position.set(0, -2.4, 2.8);
    jaw.rotation.x = 0.25;
    faceplateGroup.add(jaw);

    // Glowing Slit Eye Lenses (Iconic Angled White/Cyan Slits)
    const eyeGeo = new THREE.BoxGeometry(1.6, 0.35, 0.6);

    const leftEye = new THREE.Mesh(eyeGeo, matEyeGlow);
    leftEye.position.set(-1.5, 0.8, 4.1);
    leftEye.rotation.z = -0.22;
    leftEye.name = 'leftEye';
    faceplateGroup.add(leftEye);

    const rightEye = new THREE.Mesh(eyeGeo, matEyeGlow);
    rightEye.position.set(1.5, 0.8, 4.1);
    rightEye.rotation.z = 0.22;
    rightEye.name = 'rightEye';
    faceplateGroup.add(rightEye);

    // Dedicated Point Lights for Glowing Eyes
    const eyeLight = new THREE.PointLight(0x00f0ff, 2.2, 10);
    eyeLight.position.set(0, 0.8, 5.2);
    faceplateGroup.add(eyeLight);
    eyeLights.push(eyeLight);

    headGroup.add(faceplateGroup);

    // Floating Holographic Targeting Reticle HUD (from the photo!)
    hudReticle = new THREE.Group();
    hudReticle.name = 'hudReticle';
    hudReticle.position.set(0, 0.8, 8.5);

    // Cyan Reticle Ring
    const reticleRing = new THREE.Mesh(
      new THREE.RingGeometry(3.8, 4.1, 32),
      new THREE.MeshBasicMaterial({ color: 0x00f0ff, side: THREE.DoubleSide, transparent: true, opacity: 0.75 })
    );
    hudReticle.add(reticleRing);

    // 4 Corner Brackets: [  ]
    for (let c = 0; c < 4; c++) {
      const angle = (c * Math.PI) / 2 + Math.PI / 4;
      const bracketGeo = new THREE.RingGeometry(4.8, 5.1, 8, 1, angle - 0.3, 0.6);
      const bracket = new THREE.Mesh(bracketGeo, new THREE.MeshBasicMaterial({ color: 0x00f0ff, side: THREE.DoubleSide }));
      hudReticle.add(bracket);
    }

    headGroup.add(hudReticle);
    ironmanGroup.add(headGroup);

    // ─────────────────────────────────────────────────────────────────────────
    // 4. SHOULDERS & ARMS (Gold Biceps, Crimson Pauldrons & Gauntlets)
    // ─────────────────────────────────────────────────────────────────────────
    function buildArm(isLeft) {
      const arm = new THREE.Group();
      const sign = isLeft ? -1 : 1;

      // Shoulder Pauldron (Crimson with Gold Trim)
      const pauldronGeo = new THREE.ConeGeometry(3.8, 5.0, 6);
      const pauldron = new THREE.Mesh(pauldronGeo, matCrimson);
      pauldron.position.set(sign * 9.2, 8.8, 0.8);
      pauldron.rotation.z = sign * 0.55;
      arm.add(pauldron);

      // Bicep (Metallic Gold Armor - distinct Mark III feature)
      const bicepGeo = new THREE.CylinderGeometry(1.8, 1.6, 5.5, 16);
      const bicep = new THREE.Mesh(bicepGeo, matGold);
      bicep.position.set(sign * 9.0, 4.5, 0.6);
      bicep.rotation.z = sign * 0.1;
      arm.add(bicep);

      // Elbow Joint (Titanium)
      const elbowGeo = new THREE.SphereGeometry(1.5, 12, 12);
      const elbow = new THREE.Mesh(elbowGeo, matTitanium);
      elbow.position.set(sign * 9.3, 1.2, 0.4);
      arm.add(elbow);

      // Forearm Gauntlet (Crimson with Gold inlays)
      const forearmGeo = new THREE.CylinderGeometry(1.6, 1.3, 6.0, 16);
      const forearm = new THREE.Mesh(forearmGeo, matCrimson);
      forearm.position.set(sign * 9.5, -2.4, 0.8);
      forearm.rotation.z = -sign * 0.08;
      arm.add(forearm);

      // Hand & Repulsor Node
      const handGeo = new THREE.BoxGeometry(1.4, 1.8, 1.0);
      const hand = new THREE.Mesh(handGeo, matCrimsonDark);
      hand.position.set(sign * 9.6, -6.0, 1.0);
      arm.add(hand);

      // Glowing Palm Repulsor Disk
      const repulsorGeo = new THREE.CircleGeometry(0.5, 16);
      const repulsor = new THREE.Mesh(repulsorGeo, matArcGlow);
      repulsor.position.set(sign * 9.6, -6.0, 1.55);
      arm.add(repulsor);

      const repulsorLight = new THREE.PointLight(0x00f0ff, 1.5, 6);
      repulsorLight.position.set(sign * 9.6, -6.0, 2.0);
      arm.add(repulsorLight);
      repulsorLights.push(repulsorLight);

      return arm;
    }

    leftArmGroup = buildArm(true);
    rightArmGroup = buildArm(false);
    ironmanGroup.add(leftArmGroup);
    ironmanGroup.add(rightArmGroup);

    // ─────────────────────────────────────────────────────────────────────────
    // 5. PELVIS & CODPIECE
    // ─────────────────────────────────────────────────────────────────────────
    const pelvisGroup = new THREE.Group();
    pelvisGroup.position.set(0, -1.0, 0);

    const codpieceGeo = new THREE.BoxGeometry(5.2, 3.2, 4.0);
    const codpiece = new THREE.Mesh(codpieceGeo, matCrimson);
    pelvisGroup.add(codpiece);

    // Hip Golden Mechanical Connectors
    const hipGeo = new THREE.CylinderGeometry(1.8, 1.8, 1.4, 16);
    const leftHip = new THREE.Mesh(hipGeo, matGold);
    leftHip.rotation.z = Math.PI / 2;
    leftHip.position.set(-3.2, -0.6, 0);
    pelvisGroup.add(leftHip);

    const rightHip = new THREE.Mesh(hipGeo, matGold);
    rightHip.rotation.z = Math.PI / 2;
    rightHip.position.set(3.2, -0.6, 0);
    pelvisGroup.add(rightHip);

    ironmanGroup.add(pelvisGroup);

    // ─────────────────────────────────────────────────────────────────────────
    // 6. LEGS & BOOTS (Gold Thighs, Crimson Shins, Flight Thrusters)
    // ─────────────────────────────────────────────────────────────────────────
    function buildLeg(isLeft) {
      const leg = new THREE.Group();
      const sign = isLeft ? -1 : 1;

      // Upper Thigh Armor (Iconic Mark III Titanium Gold!)
      const thighGeo = new THREE.CylinderGeometry(2.4, 2.0, 8.5, 16);
      const thigh = new THREE.Mesh(thighGeo, matGold);
      thigh.position.set(sign * 3.4, -6.0, 0.4);
      thigh.rotation.z = sign * 0.04;
      leg.add(thigh);

      // Thigh Outer Crimson Accent Plate
      const thighTrimGeo = new THREE.BoxGeometry(0.8, 6.5, 1.8);
      const thighTrim = new THREE.Mesh(thighTrimGeo, matCrimson);
      thighTrim.position.set(sign * 5.2, -6.0, 0.5);
      leg.add(thighTrim);

      // Knee Guard Cap (Crimson)
      const kneeGeo = new THREE.BoxGeometry(2.4, 2.4, 2.0);
      const knee = new THREE.Mesh(kneeGeo, matCrimson);
      knee.position.set(sign * 3.4, -11.0, 1.2);
      knee.rotation.x = -0.15;
      leg.add(knee);

      // Shin & Calf Armor (Crimson with Gold Exhaust Vents)
      const shinGeo = new THREE.CylinderGeometry(2.0, 1.6, 8.0, 16);
      const shin = new THREE.Mesh(shinGeo, matCrimson);
      shin.position.set(sign * 3.4, -15.5, 0.6);
      leg.add(shin);

      // Armored Flight Boots
      const bootGeo = new THREE.BoxGeometry(2.6, 2.2, 5.0);
      const boot = new THREE.Mesh(bootGeo, matCrimson);
      boot.position.set(sign * 3.4, -20.0, 1.4);
      leg.add(boot);

      // Boot Gold Toe Cap
      const toeGeo = new THREE.BoxGeometry(2.4, 1.0, 1.8);
      const toe = new THREE.Mesh(toeGeo, matGold);
      toe.position.set(sign * 3.4, -20.4, 3.6);
      leg.add(toe);

      // Flight Thruster Sole Cyan Glowing Ring
      const thrusterRing = new THREE.Mesh(
        new THREE.RingGeometry(0.6, 1.0, 16),
        new THREE.MeshBasicMaterial({ color: 0x00f0ff, side: THREE.DoubleSide })
      );
      thrusterRing.rotation.x = Math.PI / 2;
      thrusterRing.position.set(sign * 3.4, -21.1, 1.4);
      leg.add(thrusterRing);

      return leg;
    }

    leftLegGroup = buildLeg(true);
    rightLegGroup = buildLeg(false);
    ironmanGroup.add(leftLegGroup);
    ironmanGroup.add(rightLegGroup);

    // ─────────────────────────────────────────────────────────────────────────
    // 7. INTERACTIVE 3D SENSOR HOTSPOTS
    // ─────────────────────────────────────────────────────────────────────────
    createHotspot('Optical HUD & Target Matrix', 'Mark III Gold-Titanium Faceplate · 120 FPS Neural Track', 0, 15.2, 5.5, ironmanGroup);
    createHotspot('Chest RT Arc Reactor', 'Clean Energy Core Generator · Output: 8.5 GW Output', 0, 6.8, 6.5, ironmanGroup);
    createHotspot('Repulsor Flight Gauntlet', 'Variable Phase Palm Repulsor · Particle Beam Ready', -9.6, -6.0, 2.2, ironmanGroup);
    createHotspot('Titanium Gold Thigh Armor', 'Nanocomposite Gold-Titanium Alloy · Deflection 99.8%', 3.4, -6.0, 2.8, ironmanGroup);
    createHotspot('Sub-Orbital Boot Thruster', 'Mach 3 Flight Capability · Repulsor Propulsion', -3.4, -20.0, 3.0, ironmanGroup);

    mainGroup.add(ironmanGroup);
  }

  // ── Mode 2: Arc Reactor Close-Up ─────────────────────────────────────────

  function buildArcReactor() {
    reactorGroup = new THREE.Group();
    reactorGroup.name = 'reactorGroup';
    reactorGroup.visible = false;

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
    const torusMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.3, metalness: 0.9 });
    const torus = new THREE.Mesh(torusGeo, torusMat);
    reactorGroup.add(torus);

    // Outer Gimbals
    const gimbal1Geo = new THREE.TorusGeometry(20, 0.6, 12, 64);
    const gimbal1Mat = new THREE.MeshBasicMaterial({ color: 0x00f0ff, wireframe: true, transparent: true, opacity: 0.6 });
    const gimbal1 = new THREE.Mesh(gimbal1Geo, gimbal1Mat);
    gimbal1.name = 'gimbal1';
    reactorGroup.add(gimbal1);

    const gimbal2Geo = new THREE.TorusGeometry(24, 0.5, 12, 64);
    const gimbal2Mat = new THREE.MeshBasicMaterial({ color: PALETTE.gold, wireframe: true, transparent: true, opacity: 0.5 });
    const gimbal2 = new THREE.Mesh(gimbal2Geo, gimbal2Mat);
    gimbal2.name = 'gimbal2';
    gimbal2.rotation.x = Math.PI / 4;
    reactorGroup.add(gimbal2);

    mainGroup.add(reactorGroup);
  }

  // ── Mode 3: Global Orbital Telemetry Globe ───────────────────────────────

  function buildGlobalGlobe() {
    globeGroup = new THREE.Group();
    globeGroup.name = 'globeGroup';
    globeGroup.visible = false;

    const globeGeo = new THREE.SphereGeometry(18, 32, 32);
    const globeMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      wireframe: true,
      transparent: true,
      opacity: 0.4,
    });
    const globeMesh = new THREE.Mesh(globeGeo, globeMat);
    globeGroup.add(globeMesh);

    const innerGlobe = new THREE.Mesh(
      new THREE.SphereGeometry(17.6, 32, 32),
      new THREE.MeshBasicMaterial({ color: 0x050d18 })
    );
    globeGroup.add(innerGlobe);

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
    const dotMat = new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide });
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
        mainGroup.rotation.x = Math.max(-0.4, Math.min(0.4, mainGroup.rotation.x + deltaY * 0.005));
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
      targetCamPos.z = Math.max(25, Math.min(95, targetCamPos.z + zoomFactor));
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
      targetCamPos.set(0, 2, 54);
      targetLookAt.set(0, 1, 0);
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
      targetCamPos.set(0, 2, 54);
      if (mainGroup) {
        mainGroup.rotation.x = 0;
        mainGroup.rotation.y = 0;
      }
    } else if (preset === 'iso') {
      targetCamPos.set(30, 18, 50);
    } else if (preset === 'top') {
      targetCamPos.set(0, 55, 8);
      if (mainGroup) {
        mainGroup.rotation.x = 0;
      }
    } else if (preset === 'orbit') {
      autoRotate = !autoRotate;
    }
    targetLookAt.set(0, 1, 0);
  }

  function setStarkTheme(enabled) {
    isStarkMode = enabled;
  }

  function setExplodeAmount(amount) {
    explodeAmount = amount;

    // Faceplate lifts up and forward
    if (faceplateGroup) {
      faceplateGroup.position.z = amount * 6;
      faceplateGroup.position.y = amount * 5;
      faceplateGroup.rotation.x = -amount * 0.7;
    }

    // Chest plates slide laterally
    if (chestGroup) {
      chestGroup.children.forEach((mesh) => {
        const norm = mesh.userData?.normal;
        if (norm) {
          mesh.position.x = mesh.position.x + norm.x * (amount * 8 - (mesh.userData._lastExplode || 0));
          mesh.position.y = mesh.position.y + norm.y * (amount * 8 - (mesh.userData._lastExplode || 0));
          mesh.position.z = mesh.position.z + norm.z * (amount * 8 - (mesh.userData._lastExplode || 0));
          mesh.userData._lastExplode = amount * 8;
        }
      });
    }

    // Arms open slightly
    if (leftArmGroup && rightArmGroup) {
      leftArmGroup.position.x = -amount * 4;
      rightArmGroup.position.x = amount * 4;
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

    // Auto-rotate if enabled
    if (autoRotate && mainGroup) {
      mainGroup.rotation.y += rotateSpeed;
    }

    // ── Full-Body Iron Man Animations ──
    if (ironmanGroup && ironmanGroup.visible) {
      // 1. Head tracks user mouse cursor smoothly!
      if (headGroup) {
        const targetHeadRotY = mouse.x * 0.45;
        const targetHeadRotX = -mouse.y * 0.25;
        headGroup.rotation.y += (targetHeadRotY - headGroup.rotation.y) * 0.06;
        headGroup.rotation.x += (targetHeadRotX - headGroup.rotation.x) * 0.06;
      }

      // 2. Subtle Idling Breathing Motion
      const breath = Math.sin(t * 2.2) * 0.15;
      chestGroup.position.y = breath;
      if (leftArmGroup && rightArmGroup) {
        leftArmGroup.rotation.x = Math.sin(t * 1.8) * 0.03;
        rightArmGroup.rotation.x = -Math.sin(t * 1.8) * 0.03;
      }

      // 3. RT Arc Reactor & Palm Repulsors Pulse
      if (chestReactorCore) {
        const arcPulse = 1.0 + Math.sin(t * 4) * 0.12 + audioPulse * 0.6;
        chestReactorCore.scale.set(arcPulse, arcPulse, 1);
      }

      // 4. Reticle HUD rotates
      if (hudReticle) {
        hudReticle.rotation.z = t * 0.35;
      }

      // 5. Eye Lights Pulse
      eyeLights.forEach((light) => {
        light.intensity = 2.2 + audioPulse * 3.0;
      });

      // 6. Repulsor Lights Pulse
      repulsorLights.forEach((light) => {
        light.intensity = 1.5 + audioPulse * 2.5;
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
        positions[i * 3 + 1] += Math.sin(t + i) * 0.012;
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

  // Public API
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
