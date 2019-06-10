import matter from 'gray-matter'

const loadPosts = () => {
  let loadedFiles = require.context(
    '../posts', true, /\.md$/)

  // process them with gray-matter
  const posts = (ctx => {
    const keys = ctx.keys();
    const values = keys.map(ctx);

    const data = keys.map((key, index) => {
      // gather the filename and turn it into a slug
      const slug = key.replace(
        /^.*[\\\/]/, ''
      ).split('.').slice(0, -1).join('.')

      // value is an object the file content
      const value = values[index]

      // parse the document and its meta data
      const document = matter(value.default)

      // make the data available as props
      return {
        document,
        slug
      }
    })

    return data
  })(loadedFiles)

  return {
    posts
  }
}

export default loadPosts