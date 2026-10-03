import type { CSSProperties } from 'react'
import { appear, beat, draw, grow, handOf, palette, rise } from '../lib/storyArtStyles'
import { Flame, Ground, Person, Wheel } from './StoryArt'

// Nine keyframed scenes on one 800 x 600 stage. Each reads its local progress from
// the inherited `--t` custom property, so the same markup serves pinned motion,
// mobile flow and the static fallback.

const glowAt = (cx: number, cy: number, from: number, to: number): CSSProperties => ({
  transformBox: 'view-box',
  transformOrigin: `${cx}px ${cy}px`,
  transform: `scale(calc(${from} + clamp(0, var(--t), 1) * ${to - from}))`,
})

const handFlame = (x: number, y: number, pose: 'offer' | 'reach', scale = 1, flip = false) => {
  const hand = handOf(x, y, pose, scale, flip)
  return { x: hand.x, y: hand.y - 7 * scale }
}

function SceneSpark() {
  return (
    <g>
      <Ground />
      <circle cx={402} cy={372} r={240} fill="url(#story-glow)" style={glowAt(402, 372, 0.75, 1.1)} />
      <Person x={340} y={505} fill={palette.personDark} rim={palette.rim} pose="offer" />
      <Person
        x={575}
        y={505}
        fill={palette.personDim}
        rim={palette.rim}
        flip
        style={{ opacity: 'calc(0.5 + clamp(0, var(--t), 1) * 0.5)' }}
      />
    </g>
  )
}

const circleOfPeople = [90, 175, 255, 470, 690]

function SceneSharing() {
  const giver = handFlame(340, 505, 'offer')
  const next = handFlame(745, 505, 'reach', 1, true)
  return (
    <g>
      <Ground />
      {circleOfPeople.map((x, index) => {
        const flame = handFlame(x, 468, 'offer', 0.55)
        return (
          <g key={x} style={appear(0.25 + index * 0.05, 0.2)}>
            <Person x={x} y={468} scale={0.55} fill={palette.personShadow} rim="#b86a3a" pose="offer" />
            <Flame x={flame.x} y={flame.y} size={0.5} glow style={appear(0.55 + index * 0.06, 0.12)} />
          </g>
        )
      })}
      <circle cx={giver.x} cy={giver.y - 20} r={160} fill="url(#story-glow)" />
      <Person x={340} y={505} fill={palette.personDark} rim={palette.rim} pose="offer" />
      <Flame x={giver.x} y={giver.y} size={1} />
      <Person x={540} y={505} fill={palette.personDim} rim={palette.rim} pose="offer" />
      <g style={rise(0.12, 0.2, 0)}>
        <Person x={745} y={505} fill={palette.personDark} rim={palette.rim} flip pose="reach" />
      </g>
      <Flame x={next.x} y={next.y} size={0.85} glow style={appear(0.5, 0.15)} />
    </g>
  )
}

const sprouts = [
  { x: 470, y: 488 },
  { x: 530, y: 478 },
  { x: 600, y: 470 },
]

function SceneTelling() {
  const symbol = { stroke: palette.amber, strokeWidth: 4, strokeLinecap: 'round', fill: 'none' } as const
  return (
    <g>
      <Ground />
      <Person x={150} y={505} fill={palette.personDark} rim={palette.rim} pose="up" />
      <path d="M196 300C230 250 210 230 250 214" pathLength={1} {...symbol} opacity=".7" style={draw(0, 0.2)} />
      <g {...symbol}>
        <g style={draw(0.12, 0.15)}>
          <circle cx={278} cy={196} r={13} pathLength={1} />
        </g>
        <path d="M300 204q10-12 20 0t20 0t20 0" pathLength={1} style={draw(0.22, 0.12)} />
        <path d="M374 214l18-32 18 32" pathLength={1} style={draw(0.3, 0.12)} />
        <path d="M426 198h38m-10-10 10 10-10 10" pathLength={1} style={draw(0.38, 0.12)} />
      </g>
      <Person x={330} y={505} fill={palette.personDim} rim={palette.rim} flip pose="point" />

      {[0, 1, 2].map((row) => (
        <path
          key={row}
          d={`M430 ${474 + row * 32}Q600 ${458 + row * 32} 800 ${474 + row * 32}`}
          stroke="#4a3528"
          strokeWidth={10}
          strokeLinecap="round"
          fill="none"
        />
      ))}
      <path
        d="M800 438Q712 470 650 492T430 524"
        stroke={palette.orange}
        strokeWidth={4}
        strokeLinecap="round"
        fill="none"
        opacity=".85"
        pathLength={1}
        style={draw(0.45, 0.3)}
      />
      <Wheel
        cx={690}
        cy={400}
        r={50}
        stroke={palette.personDeep}
        style={{ transform: 'rotate(calc(var(--t) * 240deg))' }}
      />
      {sprouts.map((sprout, index) => (
        <g key={sprout.x} style={grow(0.35 + index * 0.1, 0.25)}>
          <path d={`M${sprout.x} ${sprout.y}v-34`} stroke={palette.leaf} strokeWidth={4} strokeLinecap="round" />
          <path
            d={`M${sprout.x} ${sprout.y - 22}c-16-2-22-12-20-20 12 0 20 8 20 20Zm0-8c14-2 20-12 18-20-12 0-18 8-18 20Z`}
            fill={palette.leaf}
          />
        </g>
      ))}
      <Person x={745} y={505} fill={palette.personDark} rim={palette.rim} flip pose="reach" />
    </g>
  )
}

function SceneEngine() {
  return (
    <g>
      <Ground />
      <Person x={110} y={505} fill={palette.personWarm} rim={palette.rim} pose="offer" />
      <g style={{ transform: `translateX(calc(${beat(0, 0.4)} * 34px))` }}>
        <rect x={176} y={300} width={130} height={92} rx={6} fill={palette.sheet} />
        <g stroke={palette.personDeep} strokeWidth={2.5} fill="none" strokeLinecap="round">
          <circle cx={212} cy={346} r={22} />
          <path d="M212 324v44M190 346h44" />
          <path d="M248 330h44M248 346h30M248 362h38" />
        </g>
        <g style={draw(0.3, 0.25)}>
          <circle cx={274} cy={374} r={10} stroke={palette.orange} strokeWidth={3} fill="none" pathLength={1} />
        </g>
      </g>
      <Person x={405} y={505} fill={palette.personDark} rim={palette.rim} flip pose="reach" />
      <path
        d="M300 340Q420 290 500 410"
        stroke={palette.orange}
        strokeWidth={3}
        fill="none"
        pathLength={1}
        style={draw(0.45, 0.3)}
      />

      <rect x={445} y={330} width={155} height={120} rx={26} fill="#5a4034" />
      <rect x={470} y={270} width={26} height={66} rx={6} fill="#4a352b" />
      <rect x={470} y={395} width={60} height={42} rx={10} fill="#2a1d17" />
      <rect x={600} y={366} width={42} height={30} rx={6} fill="#4a352b" />
      <line x1={642} y1={381} x2={690} y2={400} stroke="#4a352b" strokeWidth={8} strokeLinecap="round" />
      <Wheel
        cx={690}
        cy={400}
        r={75}
        stroke={palette.personDeep}
        width={8}
        style={{ transform: 'rotate(calc(var(--t) * 300deg + 60deg))' }}
      />
      <path
        d="M483 268C485 208 380 232 408 168"
        stroke={palette.core}
        strokeWidth={7}
        strokeLinecap="round"
        fill="none"
        opacity=".55"
        pathLength={1}
        style={draw(0.25, 0.45)}
      />
    </g>
  )
}

const desks = [170, 400, 630]

function SceneLight() {
  return (
    <g>
      <Ground tone="light" />
      <circle cx={400} cy={150} r={230} fill="url(#story-glow)" style={glowAt(400, 150, 0.4, 1.2)} />
      {desks.map((x, index) => (
        <path
          key={x}
          d={`M380 200L${x - 90} 440H${x + 90}L420 200Z`}
          fill={palette.amber}
          style={{ opacity: `calc(${beat(0.2 + index * 0.12, 0.2)} * 0.12)` }}
        />
      ))}
      <circle
        cx={400}
        cy={140}
        r={58}
        fill={palette.core}
        stroke={palette.personLight}
        strokeWidth={4}
        style={{ fillOpacity: `calc(0.15 + ${beat(0, 0.3)} * 0.55)` }}
      />
      <rect x={378} y={194} width={44} height={34} rx={7} fill={palette.wood} />
      <path
        d="M380 160Q390 128 400 160T420 160"
        stroke={palette.amber}
        strokeWidth={4}
        strokeLinecap="round"
        fill="none"
        pathLength={1}
        style={draw(0, 0.25)}
      />

      {desks.map((x, index) => (
        <g key={x}>
          <Person
            x={x - 30}
            y={470}
            scale={0.72}
            fill={index === 1 ? palette.personWarm : palette.personDeep}
            pose={index === 2 ? 'reach' : 'offer'}
          />
          <rect x={x - 90} y={438} width={180} height={14} rx={7} fill={palette.wood} />
          <rect x={x - 76} y={452} width={10} height={70} rx={4} fill={palette.wood} />
          <rect x={x + 66} y={452} width={10} height={70} rx={4} fill={palette.wood} />
          <rect x={x - 12} y={424} width={38} height={14} rx={3} fill={palette.sheet} />
          <Flame x={x + 62} y={436} size={0.42} glow style={appear(0.3 + index * 0.15, 0.15)} />
        </g>
      ))}
      <g
        style={{
          opacity: `calc(${beat(0.4, 0.05)} * (1 - ${beat(0.9, 0.05)}))`,
          transform: `translate(calc(${beat(0.4, 0.45)} * 440px), calc(${beat(0.4, 0.45)} * (1 - ${beat(0.4, 0.45)}) * -160px))`,
        }}
      >
        <rect x={180} y={400} width={28} height={20} rx={3} fill={palette.paper} stroke={palette.orange} strokeWidth={2} />
      </g>
    </g>
  )
}

const topicTiles = [
  { x: 60, y: 150, label: '日本' },
  { x: 120, y: 262, label: 'a²+b²' },
  { x: 650, y: 150, label: '</>' },
  { x: 600, y: 262, label: '' },
]

const learners = [
  { x: 110, flip: false },
  { x: 250, flip: false },
  { x: 550, flip: true },
  { x: 690, flip: true },
]

const aiNodes = [
  [330, 282],
  [370, 268],
  [410, 290],
  [450, 270],
  [470, 296],
]

function SceneDistance() {
  return (
    <g>
      <Ground tone="light" />
      {learners.map((learner, index) => {
        const hand = handOf(learner.x, 545, 'offer', 0.8, learner.flip)
        const target = 330 + index * 46
        return (
          <path
            key={learner.x}
            d={`M${hand.x} ${hand.y}Q${(hand.x + target) / 2} ${hand.y - 90} ${target} 336`}
            stroke={palette.orange}
            strokeWidth={3}
            strokeLinecap="round"
            fill="none"
            pathLength={1}
            style={draw(0.12 + index * 0.07, 0.2)}
          />
        )
      })}
      <rect x={280} y={170} width={240} height={160} rx={14} fill={palette.ink} />
      <rect x={292} y={182} width={216} height={136} rx={8} fill={palette.paper} />
      <path d="M380 330h40l10 34h-60Z" fill={palette.ink} />
      <rect x={340} y={360} width={120} height={10} rx={5} fill={palette.ink} />
      {[
        [300, 192, 92, 46],
        [402, 192, 96, 46],
        [300, 248, 198, 60],
      ].map(([x, y, width, height], index) => (
        <rect
          key={index}
          x={x}
          y={y}
          width={width}
          height={height}
          rx={6}
          fill="#fde3c8"
          style={grow(0.05 + index * 0.08, 0.15, 'center')}
        />
      ))}
      <g style={appear(0.62, 0.15)}>
        <g stroke={palette.orange} strokeWidth={2.5} strokeLinecap="round">
          {aiNodes.slice(1).map(([x, y], index) => (
            <line key={x} x1={aiNodes[index][0]} y1={aiNodes[index][1]} x2={x} y2={y} />
          ))}
          <line x1={330} y1={282} x2={410} y2={290} />
          <line x1={370} y1={268} x2={450} y2={270} />
        </g>
        {aiNodes.map(([x, y]) => (
          <circle key={x} cx={x} cy={y} r={6} fill={palette.paper} stroke={palette.red} strokeWidth={3} />
        ))}
        <rect x={378} y={378} width={44} height={24} rx={12} fill={palette.ink} />
        <text x={400} y={395} textAnchor="middle" fontSize={13} fontWeight={700} fill={palette.paper}>
          AI
        </text>
      </g>
      {topicTiles.map((tile, index) => (
        <g key={tile.x} style={rise(0.2 + index * 0.08, 0.15)}>
          <rect x={tile.x} y={tile.y} width={88} height={50} rx={10} fill="#ffffff" stroke="#f1c7a0" strokeWidth={2} />
          {tile.label ? (
            <text
              x={tile.x + 44}
              y={tile.y + 32}
              textAnchor="middle"
              fontSize={19}
              fontWeight={700}
              fill={palette.ink}
            >
              {tile.label}
            </text>
          ) : (
            <g>
              <rect x={tile.x + 41} y={tile.y + 26} width={6} height={16} rx={2} fill={palette.wood} />
              <circle cx={tile.x + 44} cy={tile.y + 20} r={12} fill={palette.leaf} />
            </g>
          )}
        </g>
      ))}
      {learners.map((learner, index) => (
        <Person
          key={learner.x}
          x={learner.x}
          y={545}
          scale={0.8}
          flip={learner.flip}
          fill={index % 2 ? palette.personWarm : palette.personDeep}
          pose="offer"
        />
      ))}
    </g>
  )
}

const frontRow = [
  { x: 110, flip: false },
  { x: 255, flip: false },
  { x: 545, flip: true },
  { x: 690, flip: true },
]
const backRow = [
  { x: 190, flip: false },
  { x: 320, flip: false },
  { x: 480, flip: true },
  { x: 610, flip: true },
]

function SceneCommunity() {
  const hub = { x: 400, y: 300 }
  const people = [
    ...backRow.map((person) => ({ ...person, y: 405, scale: 0.55 })),
    ...frontRow.map((person) => ({ ...person, y: 530, scale: 0.75 })),
  ]
  return (
    <g>
      <g opacity=".16" stroke={palette.wood} strokeWidth={4} fill="none">
        <Wheel cx={110} cy={130} r={42} stroke={palette.wood} />
        <circle cx={690} cy={110} r={34} />
        <rect x={672} y={146} width={36} height={22} rx={5} />
        <rect x={340} y={40} width={120} height={80} rx={10} />
      </g>
      <Ground tone="light" />
      {people.map((person, index) => {
        const hand = handOf(person.x, person.y, 'offer', person.scale, person.flip)
        return (
          <path
            key={`line-${index}`}
            d={`M${hand.x} ${hand.y}Q${(hand.x + hub.x) / 2} ${Math.min(hand.y, hub.y) - 30} ${hub.x} ${hub.y}`}
            stroke={palette.orange}
            strokeWidth={2.5}
            strokeLinecap="round"
            fill="none"
            opacity=".8"
            pathLength={1}
            style={draw(0.1 + index * 0.05, 0.2)}
          />
        )
      })}
      {people.map((person, index) => {
        const flame = handFlame(person.x, person.y, 'offer', person.scale, person.flip)
        return (
          <g key={`${person.x}-${person.y}`}>
            <Person
              x={person.x}
              y={person.y}
              scale={person.scale}
              flip={person.flip}
              fill={index < backRow.length ? palette.personSoft : index % 2 ? palette.personWarm : palette.personDeep}
              pose="offer"
            />
            <Flame
              x={flame.x}
              y={flame.y}
              size={person.scale * 0.7}
              style={appear(0.2 + ((index * 3) % people.length) * 0.06, 0.12)}
            />
          </g>
        )
      })}
    </g>
  )
}

function SceneFlama() {
  const learnerHand = handOf(150, 545, 'offer', 0.8)
  const creatorHand = handOf(650, 545, 'offer', 0.8, true)
  const label = (x: number, y: number, text: string, start: number) => (
    <g style={appear(start, 0.15)}>
      <rect x={x - text.length * 4.6 - 12} y={y - 17} width={text.length * 9.2 + 24} height={28} rx={14} fill="#ffffff" stroke="#f1c7a0" />
      <text x={x} y={y + 2} textAnchor="middle" fontSize={14} fontWeight={600} fill={palette.ink}>
        {text}
      </text>
    </g>
  )
  return (
    <g>
      <Ground tone="light" />
      <path
        d={`M${learnerHand.x} ${learnerHand.y}Q250 300 330 250M470 250Q560 300 ${creatorHand.x} ${creatorHand.y}`}
        stroke={palette.orange}
        strokeWidth={3}
        strokeLinecap="round"
        fill="none"
        pathLength={1}
        style={draw(0.05, 0.3)}
      />
      <g>
        <rect
          x={305}
          y={160}
          width={190}
          height={120}
          rx={14}
          fill="#fde3c8"
          style={{ transformBox: 'fill-box', transform: `rotate(calc(${beat(0, 0.3)} * -9deg))`, transformOrigin: 'center' }}
        />
        <rect
          x={305}
          y={160}
          width={190}
          height={120}
          rx={14}
          fill="#fcd2ae"
          style={{ transformBox: 'fill-box', transform: `rotate(calc(${beat(0, 0.3)} * 8deg))`, transformOrigin: 'center' }}
        />
        <rect x={305} y={160} width={190} height={120} rx={14} fill="#ffffff" stroke="#f1c7a0" strokeWidth={2} />
        <text x={400} y={224} textAnchor="middle" fontSize={32} fontWeight={700} fill={palette.ink}>
          日本語
        </text>
        <text x={400} y={252} textAnchor="middle" fontSize={13} fill={palette.wood}>
          にほんご · tiếng Nhật
        </text>
      </g>
      <g
        style={{
          opacity: `calc(${beat(0.2, 0.05)} * (1 - ${beat(0.6, 0.05)}))`,
          transform: `translate(calc(${beat(0.25, 0.35)} * -150px), calc(${beat(0.25, 0.35)} * -150px))`,
        }}
      >
        <rect x={creatorHand.x - 50} y={creatorHand.y - 26} width={56} height={38} rx={7} fill="#ffffff" stroke={palette.orange} strokeWidth={2} />
      </g>
      <g style={appear(0.5, 0.15)}>
        <rect x={470} y={296} width={150} height={40} rx={12} fill="#ffffff" stroke="#f1c7a0" strokeWidth={2} />
        <text x={545} y={321} textAnchor="middle" fontSize={13} fill={palette.ink}>
          Góp ý: thêm một ví dụ
        </text>
      </g>
      <Person x={150} y={545} scale={0.8} fill={palette.personDeep} pose="offer" />
      <Person x={650} y={545} scale={0.8} flip fill={palette.personWarm} pose="offer" />
      <Person x={430} y={560} scale={0.8} flip fill={palette.personLight} pose="reach" />
      {label(150, 370, 'Học', 0.1)}
      {label(650, 370, 'Chia sẻ', 0.2)}
      {label(430, 388, 'Cùng phát triển', 0.45)}
    </g>
  )
}

const communityFlames = Array.from({ length: 9 }, (_, index) => {
  const x = 90 + index * 77.5
  return { x, y: 330 + ((x - 400) / 310) ** 2 * 70 }
})

function SceneYourTurn() {
  return (
    <g>
      <Ground tone="light" />
      {communityFlames.map((flame, index) => (
        <Flame key={flame.x} x={flame.x} y={flame.y} size={0.45} glow style={{ opacity: 0.75, ...appear(index * 0.02, 0.1) }} />
      ))}
      <g
        style={{
          transformBox: 'view-box',
          transformOrigin: '400px 150px',
          transform: `translateY(calc(${beat(0, 0.5)} * -12px)) scale(calc(1 - ${beat(0, 0.5)} * 0.12))`,
        }}
      >
        <image href="/logo.png" x={330} y={40} width={140} height={140} />
        <text x={400} y={230} textAnchor="middle" fontSize={46} fontWeight={900} fill="url(#story-wordmark)">
          Flama
        </text>
      </g>
      <g style={{ transform: `translateY(calc((1 - ${beat(0, 0.35)}) * 70px))` }}>
        <path d="M336 600C330 540 336 496 360 470H440C464 496 470 540 464 600Z" fill="url(#story-skin)" />
        {[
          [344, 410, -12, 72],
          [372, 392, -4, 86],
          [402, 392, 4, 86],
          [430, 408, 12, 72],
        ].map(([x, y, angle, height]) => (
          <rect
            key={x}
            x={x}
            y={y}
            width={26}
            height={height}
            rx={13}
            fill={palette.personSoft}
            transform={`rotate(${angle} ${x + 13} ${y + height})`}
          />
        ))}
        <rect x={337} y={470} width={26} height={76} rx={13} fill="url(#story-skin)" transform="rotate(-42 350 546)" />
        <path d="M372 548Q398 530 428 534" stroke={palette.personLight} strokeWidth={3} fill="none" strokeLinecap="round" opacity=".5" />
      </g>
    </g>
  )
}

const storyScenes = [
  SceneSpark,
  SceneSharing,
  SceneTelling,
  SceneEngine,
  SceneLight,
  SceneDistance,
  SceneCommunity,
  SceneFlama,
  SceneYourTurn,
]

/** Renders chapter `index`'s scene; progress comes from the inherited `--t`. */
export function StoryScene({ index }: { index: number }) {
  const Scene = storyScenes[index]
  return <Scene />
}
