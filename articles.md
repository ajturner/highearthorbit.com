---
layout: articles
title: Articles
permalink: /articles/
banner: https://farm8.staticflickr.com/7348/11452221493_8523f98888_b_d.jpg
---

<h2>Articles by Andrew Turner</h2>
<ul>
  {% for post in site.posts %}
    <li>
      <a href="{{ post.url }}">{{ post.title }}</a>
    </li>
  {% endfor %}
</ul>
