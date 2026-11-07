# Site rules shared with the WordPress publisher (scripts/heo/publish.py).
#
# 1. Items with `hidden: true` never go live. On staging (heo.staging: true) they are
#    built and marked as drafts so they can be reviewed; otherwise they are dropped.
#    Photo albums that are hidden or listed in _data/flickr_exclude.yml are always
#    dropped, since exclusion there is about privacy, not review.
#    Projects backed by one of your own repositories (heo.github_user) are built only
#    when the repository has the `portfolio` topic (same rule as
#    scripts/heo/content.py portfolio_excluded).
# 2. Archive posts imported from WordPress contain root-relative links such as
#    /assets/uploads/... When the site is served under a base path (a GitHub Pages
#    project site), those links are rewritten to include it. Layouts follow the same
#    convention: they write root-relative paths and never use relative_url.

module HEO
  class Visibility < Jekyll::Generator
    priority :highest

    def generate(site)
      staging = site.config.dig("heo", "staging") == true
      excluded = Array(site.data.dig("flickr_exclude", "albums")).map { |a| a["id"].to_s }
      user = site.config.dig("heo", "github_user").to_s.downcase
      site.collections.each do |name, collection|
        # External articles link out; `url` in their front matter is the canonical URL,
        # which Jekyll's own doc.url would shadow in templates.
        collection.docs.each { |doc| doc.data["href"] = doc.data["url"] } if name == "external"
        collection.docs.reject! do |doc|
          hidden = doc.data["hidden"] == true
          if name == "photos"
            hidden || excluded.include?(doc.data["flickr_id"].to_s)
          elsif name == "projects" && HEO.portfolio_excluded?(doc, user)
            true
          else
            doc.data["draft_badge"] = true if hidden
            hidden && !staging
          end
        end
      end
    end
  end

  def self.portfolio_excluded?(doc, user)
    owner = doc.data["github"].to_s.split("/").first.to_s.downcase
    return false if user.empty? || owner != user
    topics = Array((doc.data["synced"] || {})["topics"]).map { |t| t.to_s.downcase }
    !topics.include?("portfolio")
  end

  ROOT_RELATIVE = /(\s(?:href|src|srcset|poster)=["'])\/(?!\/)/

  def self.prefix_baseurl(item)
    base = item.site.config["baseurl"].to_s.chomp("/")
    return if base.empty? || item.output.nil?
    return unless item.output_ext == ".html" || item.output_ext == ".xml"
    item.output = item.output.gsub(ROOT_RELATIVE) { "#{Regexp.last_match(1)}#{base}/" }
  end
end

Jekyll::Hooks.register [:pages, :documents], :post_render do |item|
  HEO.prefix_baseurl(item)
end
