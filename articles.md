---
layout: articles
title: Articles
permalink: /articles/
banner: https://farm8.staticflickr.com/7348/11452221493_8523f98888_b_d.jpg
---

<ul>
  {% for post in site.posts %}
    <li>
      <a href="{{ post.url }}">{{ post.title }}</a>
    </li>
  {% endfor %}
</ul>
