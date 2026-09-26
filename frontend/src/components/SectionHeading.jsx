export default function SectionHeading({
  eyebrow,
  title,
  description,
  align = 'left',
  className = '',
  as = 'h2',
}) {
  const Heading = as

  return (
    <div className={`section-heading section-heading-${align} ${className}`}>
      {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
      <Heading>{title}</Heading>
      {description ? <p className="section-description">{description}</p> : null}
    </div>
  )
}
