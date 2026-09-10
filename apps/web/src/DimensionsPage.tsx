import { DIMENSIONS } from './dimensions'
import './App.css'

export default function DimensionsPage() {
  return (
    <div className="dimensions">
      <p className="section-heading">Label dimensions</p>
      <p className="dimensions__intro">
        Each meeting is tagged along these axes. Values are assigned by the LLM labeler — this page explains what they mean.
      </p>
      <div className="dimensions__grid">
        {DIMENSIONS.map((dim) => (
          <article key={dim.key} className="dimension-card">
            <h2 className="dimension-card__title">{dim.title}</h2>
            <p className="dimension-card__why">{dim.why}</p>
            <ul className="dimension-card__enums">
              {dim.enums.map((e) => (
                <li key={e.key} className="enum-row">
                  <span className="enum-row__label">{e.label}</span>
                  <span className="enum-row__gloss">{e.gloss}</span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </div>
  )
}
